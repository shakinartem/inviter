import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { usePlatforms } from "@/hooks/use-proxy-candidates";

export default function PlatformsPage() {
  const { data, isLoading } = usePlatforms();

  if (isLoading) {
    return <div className="text-center py-8 text-muted-foreground">Загрузка...</div>;
  }

  const platforms = data?.platforms || [];

  const statusColors: Record<string, "default" | "secondary" | "destructive" | "outline"> = {
    active: "default",
    planned: "secondary",
    not_implemented: "outline",
    disabled: "destructive",
  };

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Платформы</h1>
        <p className="text-muted-foreground mt-1">
          Архитектурная основа для поддержки нескольких мессенджеров и соцсетей.
        </p>
      </div>

      <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 text-blue-800">
        <p className="text-sm">
          ℹ️ Сейчас боевой инвайтинг реализуется только для поддерживаемых платформ.
          Остальные платформы добавлены как архитектурная основа и требуют отдельной
          интеграции с соблюдением правил соответствующей платформы.
        </p>
      </div>

      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        {platforms.map((p) => (
          <Card key={p.platform} className={p.status === "active" ? "border-green-200" : ""}>
            <CardHeader className="pb-2">
              <div className="flex items-center justify-between">
                <CardTitle className="text-lg">{p.display_name}</CardTitle>
                <Badge variant={statusColors[p.status] || "outline"}>{p.status}</Badge>
              </div>
            </CardHeader>
            <CardContent>
              {/* Proxy */}
              <div className="mb-3">
                <span className="text-xs text-muted-foreground font-medium">Прокси:</span>
                <span className="text-sm ml-2">
                  {p.supports_proxy ? "✅ Поддерживает" : "❌ Не поддерживает"}
                </span>
                {p.supported_proxy_types.length > 0 && (
                  <div className="flex flex-wrap gap-1 mt-1">
                    {p.supported_proxy_types.map((t: string) => (
                      <Badge key={t} variant="outline" className="text-xs">
                        {t}
                      </Badge>
                    ))}
                  </div>
                )}
              </div>

              {/* Actions */}
              <div className="mb-3 space-y-1">
                <div className="flex items-center gap-2 text-sm">
                  <span className={p.supports_invites ? "text-green-600" : "text-gray-400"}>
                    {p.supports_invites ? "✅" : "⬜"} Инвайтинг
                  </span>
                </div>
                <div className="flex items-center gap-2 text-sm">
                  <span className={p.supports_messages ? "text-green-600" : "text-gray-400"}>
                    {p.supports_messages ? "✅" : "⬜"} Сообщения
                  </span>
                </div>
                <div className="flex items-center gap-2 text-sm">
                  <span className={p.supports_group_sources ? "text-green-600" : "text-gray-400"}>
                    {p.supports_group_sources ? "✅" : "⬜"} Групповые источники
                  </span>
                </div>
                <div className="flex items-center gap-2 text-sm">
                  <span className={p.supports_member_parsing ? "text-green-600" : "text-gray-400"}>
                    {p.supports_member_parsing ? "✅" : "⬜"} Парсинг участников
                  </span>
                </div>
              </div>

              {/* Notes */}
              {p.notes && (
                <p className="text-xs text-muted-foreground italic mt-2">
                  {p.notes}
                </p>
              )}
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}