
import { useEffect, useState } from "react";
import type { LiveTopic } from "../api/client";
import { subscribeLive } from "../api/websocket";

const REFRESH_MS = 60_000;

function matchesScope(
  messageScope: string | null,
  widgetScope?: string | null
): boolean {
  // 범위 지정이 없는 위젯은 해당 topic 전체 수신
  if (widgetScope == null) return true;

  // 서버의 공통 범위 메시지는 모든 관련 위젯 갱신
  if (messageScope == null) return true;

  return (
    messageScope.trim().toUpperCase() ===
    widgetScope.trim().toUpperCase()
  );
}

export function useWidgetRefresh(
  topic: LiveTopic | null,
  scope?: string | null
): number {
  const [version, setVersion] = useState(0);

  useEffect(() => {
    const refresh = () => {
      setVersion((previous) => previous + 1);
    };

    // 1. WebSocket 메시지 구독
    const unsubscribe = topic
      ? subscribeLive((message) => {
          if (message.topic !== topic) return;

          if (!matchesScope(message.scope, scope)) {
            return;
          }

          console.log(
            `[실시간 갱신] ${topic}`,
            message.scope
          );

          refresh();
        })
      : null;

    // 2. 60초마다 자동 갱신
    const timer = window.setInterval(() => {
      if (document.visibilityState !== "visible") {
        return;
      }

      console.log(
        `[60초 자동 갱신] ${topic ?? "facilities"}`
      );

      refresh();
    }, REFRESH_MS);

    // 3. 다른 브라우저 탭에서 돌아오면 갱신
    const onVisibilityChange = () => {
      if (document.visibilityState === "visible") {
        refresh();
      }
    };

    document.addEventListener(
      "visibilitychange",
      onVisibilityChange
    );

    // 4. 컴포넌트 해제 시 구독 및 타이머 정리
    return () => {
      unsubscribe?.();
      window.clearInterval(timer);

      document.removeEventListener(
        "visibilitychange",
        onVisibilityChange
      );
    };
  }, [topic, scope]);

  return version;
}
