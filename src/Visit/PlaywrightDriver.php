<?php

declare(strict_types=1);

namespace YandexSites\Visit;

/**
 * Посещение страниц через headless Chromium: запускает tools/render-page.js (Node.js + Playwright),
 * передаёт задания в JSON через stdin и читает результаты построчно из stdout.
 */
final class PlaywrightDriver implements DriverInterface
{
    private string $script;

    public function __construct(private string $node = 'node', ?string $script = null)
    {
        $this->script = $script ?? dirname(__DIR__, 2) . '/tools/render-page.js';
    }

    public function name(): string
    {
        return 'playwright';
    }

    /**
     * Проверяет, что Node.js, модуль playwright и Chromium доступны.
     *
     * @return array{ok: bool, message: string}
     */
    public function probe(?string $browserPath = null): array
    {
        if (!is_file($this->script)) {
            return ['ok' => false, 'message' => 'не найден скрипт ' . $this->script];
        }
        $env = $this->env($browserPath);
        $process = @proc_open([$this->node, $this->script, '--check'], [0 => ['pipe', 'r'], 1 => ['pipe', 'w'], 2 => ['pipe', 'w']], $pipes, null, $env);
        if (!is_resource($process)) {
            return ['ok' => false, 'message' => 'не удалось запустить ' . $this->node];
        }
        fclose($pipes[0]);
        $out = (string) stream_get_contents($pipes[1]);
        $err = (string) stream_get_contents($pipes[2]);
        fclose($pipes[1]);
        fclose($pipes[2]);
        $code = proc_close($process);

        $data = json_decode(trim((string) strrchr("\n" . trim($out), "\n")), true);
        if (is_array($data) && isset($data['ok'])) {
            if ($data['ok']) {
                return ['ok' => true, 'message' => sprintf('%s %s, Chromium: %s', $data['module'] ?? 'playwright', $data['version'] ?? '', $data['executablePath'] ?? '')];
            }

            return ['ok' => false, 'message' => (string) ($data['error'] ?? 'неизвестная ошибка')];
        }

        return ['ok' => false, 'message' => trim($err !== '' ? $err : $out) !== '' ? trim($err !== '' ? $err : $out) : sprintf('node завершился с кодом %d', $code)];
    }

    public function visit(array $jobs, array $options, ?callable $onResult = null): array
    {
        $byId = [];
        $payloadJobs = [];
        foreach ($jobs as $job) {
            $byId[$job->id] = $job;
            $payloadJobs[] = [
                'id' => $job->id,
                'url' => $job->url,
                'referer' => $job->referer,
                'userAgent' => $job->userAgent,
                'proxy' => $job->proxyUrl,
                'htmlFile' => $job->htmlFile,
                'screenshotFile' => $job->screenshotFile,
            ];
        }
        $payload = json_encode([
            'options' => [
                'timeout' => (int) ($options['timeout'] ?? 30),
                'wait_ms' => (int) ($options['wait_ms'] ?? 0),
                'concurrency' => (int) ($options['concurrency'] ?? 1),
                'delay_ms' => (int) ($options['delay_ms'] ?? 0),
                'verify_ssl' => (bool) ($options['verify_ssl'] ?? true),
                'full_page' => (bool) ($options['full_page'] ?? false),
                'max_bytes' => max(65536, (int) ($options['max_bytes'] ?? 2 * 1024 * 1024)),
                'resolve' => array_values((array) ($options['resolve'] ?? [])),
                'browser_path' => $options['browser_path'] ?? null,
            ],
            'jobs' => $payloadJobs,
        ], JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES | JSON_THROW_ON_ERROR);

        $process = proc_open(
            [$this->node, $this->script],
            [0 => ['pipe', 'r'], 1 => ['pipe', 'w'], 2 => ['pipe', 'w']],
            $pipes,
            null,
            $this->env($options['browser_path'] ?? null),
        );
        if (!is_resource($process)) {
            throw new \RuntimeException('Не удалось запустить ' . $this->node . ' ' . $this->script);
        }
        fwrite($pipes[0], $payload);
        fclose($pipes[0]);
        stream_set_blocking($pipes[1], false);
        stream_set_blocking($pipes[2], false);

        $results = [];
        $stdout = '';
        $stderr = '';
        $open = [$pipes[1], $pipes[2]];
        while ($open !== []) {
            $read = $open;
            $write = null;
            $except = null;
            if (stream_select($read, $write, $except, 1) === false) {
                break;
            }
            foreach ($read as $stream) {
                $chunk = fread($stream, 65536);
                if ($chunk === false || $chunk === '') {
                    if (feof($stream)) {
                        $open = array_values(array_filter($open, static fn ($s) => $s !== $stream));
                    }
                    continue;
                }
                if ($stream === $pipes[1]) {
                    $stdout .= $chunk;
                    while (($pos = strpos($stdout, "\n")) !== false) {
                        $line = trim(substr($stdout, 0, $pos));
                        $stdout = substr($stdout, $pos + 1);
                        $this->handleLine($line, $byId, $results, $onResult);
                    }
                } else {
                    $stderr .= $chunk;
                }
            }
        }
        if (trim($stdout) !== '') {
            $this->handleLine(trim($stdout), $byId, $results, $onResult);
        }
        fclose($pipes[1]);
        fclose($pipes[2]);
        $code = proc_close($process);

        foreach ($jobs as $job) {
            if (!isset($results[$job->id])) {
                $tail = trim((string) substr($stderr, -400));
                $results[$job->id] = [
                    'ok' => false,
                    'error' => sprintf('нет результата от render-page.js (код %d)%s', $code, $tail !== '' ? ': ' . $tail : ''),
                    'status' => null,
                    'final_url' => '',
                    'title' => '',
                ];
                if ($onResult !== null) {
                    $onResult($job, $results[$job->id]);
                }
            }
        }

        return $results;
    }

    /**
     * @param array<string, VisitJob> $byId
     * @param array<string, array<string, mixed>> $results
     */
    private function handleLine(string $line, array $byId, array &$results, ?callable $onResult): void
    {
        if ($line === '') {
            return;
        }
        $data = json_decode($line, true);
        if (!is_array($data) || !isset($data['id']) || !isset($byId[$data['id']])) {
            return;
        }
        $result = [
            'ok' => (bool) ($data['ok'] ?? false),
            'error' => (string) ($data['error'] ?? ''),
            'status' => isset($data['status']) ? (int) $data['status'] : null,
            'final_url' => (string) ($data['finalUrl'] ?? ''),
            'title' => (string) ($data['title'] ?? ''),
        ];
        $results[$data['id']] = $result;
        if ($onResult !== null) {
            $onResult($byId[$data['id']], $result);
        }
    }

    /**
     * @return array<string, string>
     */
    private function env(?string $browserPath): array
    {
        $env = [];
        foreach (['PATH', 'HOME', 'PLAYWRIGHT_BROWSERS_PATH', 'NODE_PATH', 'TMPDIR', 'TEMP', 'TMP', 'SYSTEMROOT', 'APPDATA', 'LOCALAPPDATA', 'USERPROFILE'] as $name) {
            $value = getenv($name);
            if ($value !== false) {
                $env[$name] = $value;
            }
        }
        if ($browserPath !== null && $browserPath !== '') {
            $env['YS_BROWSER_PATH'] = $browserPath;
        }

        return $env;
    }
}
