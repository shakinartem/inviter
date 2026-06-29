import { useState, type ChangeEvent } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { toast } from "sonner";
import { useImportMtproto, useImportText, useProxyCandidates, useCheckCandidate, useBulkCheckCandidates, useApproveCandidate, useRejectCandidate, useDeleteCandidate } from "@/hooks/use-proxy-candidates";
import { formatDistanceToNow } from "date-fns";
import { ru } from "date-fns/locale";

export default function MtprotoImportPage() {
  const [mtprotoText, setMtprotoText] = useState("");
  const [mtprotoSourceName, setMtprotoSourceName] = useState("");
  const [proxyText, setProxyText] = useState("");
  const [proxySourceName, setProxySourceName] = useState("");

  const importMtproto = useImportMtproto();
  const importText = useImportText();
  const { data: candidatesData } = useProxyCandidates();
  const checkCandidate = useCheckCandidate();
  const bulkCheck = useBulkCheckCandidates();
  const approve = useApproveCandidate();
  const reject = useRejectCandidate();
  const del = useDeleteCandidate();

  const candidates = candidatesData?.items || [];

  const handleImportMtproto = async () => {
    if (!mtprotoText.trim()) {
      toast.error("Введите текст с MTProto-ссылками");
      return;
    }
    try {
      const result = await importMtproto.mutateAsync({
        text: mtprotoText,
        source_name: mtprotoSourceName || null,
      });
      toast.success(`Импортировано ${result.imported_count} MTProto-прокси`);
      setMtprotoText("");
    } catch {
      toast.error("Ошибка импорта MTProto");
    }
  };

  const handleImportProxy = async () => {
    if (!proxyText.trim()) {
      toast.error("Введите текст с прокси");
      return;
    }
    try {
      const result = await importText.mutateAsync({
        text: proxyText,
        source_name: proxySourceName || null,
      });
      toast.success(`Импортировано ${result.imported_count} прокси`);
      setProxyText("");
    } catch {
      toast.error("Ошибка импорта прокси");
    }
  };

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Импорт прокси</h1>
        <p className="text-muted-foreground mt-1">
          Импортируйте MTProto-прокси или обычные прокси (SOCKS5, HTTP) как кандидатов.
          После импорта проверьте и одобрите их.
        </p>
      </div>

      {/* Warning Banners */}
      <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4 text-yellow-800">
        <p className="text-sm">
          ⚠️ <strong>Публичные прокси нестабильны</strong> и могут быть небезопасны.
          Не назначайте их важным аккаунтам без проверки.
        </p>
        <p className="text-sm mt-1">
          ℹ️ <strong>MTProto-прокси</strong> подходят только для Telegram и не являются SOCKS5/HTTP.
        </p>
        <p className="text-sm mt-1">
          🛡️ Система не должна использоваться для спама или обхода правил платформ.
        </p>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        {/* MTProto Import */}
        <Card>
          <CardHeader>
            <CardTitle>Импорт MTProto-прокси</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <p className="text-sm text-muted-foreground">
              Вставьте MTProto-ссылки:
            </p>
            <ul className="text-xs text-muted-foreground list-disc list-inside">
              <li>tg://proxy?server=HOST&port=PORT&secret=SECRET</li>
              <li>https://t.me/proxy?server=HOST&port=PORT&secret=SECRET</li>
              <li>Параметры могут быть в любом порядке</li>
            </ul>
            <Textarea
              placeholder="tg://proxy?server=1.2.3.4&port=443&secret=abc..."
              value={mtprotoText}
              onChange={(e: ChangeEvent<HTMLTextAreaElement>) => setMtprotoText(e.target.value)}
              rows={5}
            />
            <Input
              placeholder="Название источника (опционально)"
              value={mtprotoSourceName}
              onChange={(e: ChangeEvent<HTMLInputElement>) => setMtprotoSourceName(e.target.value)}
            />
            <Button
              onClick={handleImportMtproto}
              disabled={importMtproto.isPending || !mtprotoText.trim()}
              className="w-full"
            >
              {importMtproto.isPending ? "Импорт..." : "Импортировать MTProto"}
            </Button>
          </CardContent>
        </Card>

        {/* Text Proxy Import */}
        <Card>
          <CardHeader>
            <CardTitle>Импорт прокси (SOCKS5/HTTP)</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <p className="text-sm text-muted-foreground">
              Вставьте прокси (по одному на строку):
            </p>
            <ul className="text-xs text-muted-foreground list-disc list-inside">
              <li>ip:port</li>
              <li>socks5://user:pass@host:port</li>
              <li>http://host:port</li>
              <li>socks5://host:port</li>
            </ul>
            <Textarea
              placeholder="socks5://user:pass@1.2.3.4:1080&#10;http://5.6.7.8:3128&#10;9.10.11.12:4153"
              value={proxyText}
              onChange={(e: ChangeEvent<HTMLTextAreaElement>) => setProxyText(e.target.value)}
              rows={5}
            />
            <Input
              placeholder="Название источника (опционально)"
              value={proxySourceName}
              onChange={(e: ChangeEvent<HTMLInputElement>) => setProxySourceName(e.target.value)}
            />
            <Button
              onClick={handleImportProxy}
              disabled={importText.isPending || !proxyText.trim()}
              className="w-full"
            >
              {importText.isPending ? "Импорт..." : "Импортировать прокси"}
            </Button>
          </CardContent>
        </Card>
      </div>

      {/* Candidates Table */}
      <Card>
        <CardHeader>
          <CardTitle>Кандидаты ({candidates.length})</CardTitle>
        </CardHeader>
        <CardContent>
          {candidates.length === 0 ? (
            <p className="text-muted-foreground text-sm py-8 text-center">
              Нет кандидатов. Импортируйте прокси выше.
            </p>
          ) : (
            <>
              {candidates.filter(c => c.status === "new").length > 0 && (
                <Button
                  variant="outline"
                  size="sm"
                  className="mb-4"
                  onClick={() => {
                    const newIds = candidates
                      .filter(c => c.status === "new")
                      .map(c => c.id);
                    if (newIds.length > 0) {
                      bulkCheck.mutate({ ids: newIds });
                      toast.info(`Проверка ${newIds.length} кандидатов...`);
                    }
                  }}
                  disabled={bulkCheck.isPending}
                >
                  {bulkCheck.isPending ? "Проверка..." : "Проверить все новые"}
                </Button>
              )}
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b">
                      <th className="text-left py-2 px-2">Тип</th>
                      <th className="text-left py-2 px-2">Хост</th>
                      <th className="text-left py-2 px-2">Порт</th>
                      <th className="text-left py-2 px-2">Статус</th>
                      <th className="text-left py-2 px-2">Score</th>
                      <th className="text-left py-2 px-2">Latency</th>
                      <th className="text-left py-2 px-2">Источник</th>
                      <th className="text-left py-2 px-2">Проверен</th>
                      <th className="text-right py-2 px-2">Действия</th>
                    </tr>
                  </thead>
                  <tbody>
                    {candidates.map((c) => (
                      <tr key={c.id} className="border-b hover:bg-gray-50">
                        <td className="py-2 px-2">
                          <Badge variant="outline">{c.proxy_type}</Badge>
                        </td>
                        <td className="py-2 px-2 font-mono text-xs">{c.host}</td>
                        <td className="py-2 px-2 font-mono text-xs">{c.port}</td>
                        <td className="py-2 px-2">
                          <Badge
                            variant={
                              c.status === "alive" ? "default" :
                              c.status === "dead" ? "destructive" :
                              c.status === "approved" ? "default" :
                              c.status === "rejected" ? "secondary" :
                              c.status === "checking" ? "outline" :
                              "secondary"
                            }
                          >
                            {c.status}
                          </Badge>
                        </td>
                        <td className="py-2 px-2">{c.score}</td>
                        <td className="py-2 px-2 font-mono text-xs">
                          {c.latency_ms ? `${c.latency_ms.toFixed(0)}ms` : "-"}
                        </td>
                        <td className="py-2 px-2 text-xs">{c.source_type}</td>
                        <td className="py-2 px-2 text-xs">
                          {c.last_checked_at
                            ? formatDistanceToNow(new Date(c.last_checked_at), { addSuffix: true, locale: ru })
                            : "-"}
                        </td>
                        <td className="py-2 px-2 text-right">
                          <div className="flex gap-1 justify-end">
                            <Button
                              variant="outline"
                              size="sm"
                              className="h-7 text-xs"
                              onClick={() => checkCandidate.mutate(c.id)}
                              disabled={checkCandidate.isPending}
                            >
                              Check
                            </Button>
                            {c.status !== "approved" && (
                              <Button
                                variant="default"
                                size="sm"
                                className="h-7 text-xs"
                                onClick={() => approve.mutate(c.id)}
                              >
                                Approve
                              </Button>
                            )}
                            {c.status !== "rejected" && c.status !== "approved" && (
                              <Button
                                variant="secondary"
                                size="sm"
                                className="h-7 text-xs"
                                onClick={() => reject.mutate(c.id)}
                              >
                                Reject
                              </Button>
                            )}
                            {c.status !== "approved" && (
                              <Button
                                variant="destructive"
                                size="sm"
                                className="h-7 text-xs"
                                onClick={() => del.mutate(c.id)}
                              >
                                Del
                              </Button>
                            )}
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          )}
        </CardContent>
      </Card>

      {/* Local Adapter Helper */}
      <Card>
        <CardHeader>
          <CardTitle>Nekobox / Local Adapter</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2">
          <p className="text-sm">
            Для использования Nekobox (или sing-box/xray) в Docker:
          </p>
          <ul className="text-sm list-disc list-inside space-y-1">
            <li>Запустите Nekobox с proxy-портом (например, <code className="bg-gray-100 px-1 rounded">:2080</code>)</li>
            <li>В Inviter укажите <code className="bg-gray-100 px-1 rounded">host.docker.internal:2080</code></li>
            <li>Тип: <code className="bg-gray-100 px-1 rounded">socks5</code> или <code className="bg-gray-100 px-1 rounded">http</code> (mixed)</li>
          </ul>
          <div className="bg-yellow-50 border border-yellow-200 rounded p-3 text-sm text-yellow-800 mt-3">
            <strong>⚠️ Важно:</strong> Если backend запущен в Docker, <code className="bg-yellow-100 px-1 rounded">127.0.0.1</code> внутри контейнера — это не Windows-хост.
            Используйте <code className="bg-yellow-100 px-1 rounded">host.docker.internal</code> для доступа к прокси на хосте.
          </div>
        </CardContent>
      </Card>
    </div>
  );
}