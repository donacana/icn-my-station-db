import { useId, useMemo } from "react";
import type { Hall, Terminal } from "../../../api/congestion";
import "./Terminal3D.css";

interface Props {
  terminal: Terminal;
  halls: Hall[];
  selectedId: string | null;
  onSelect: (id: string) => void;
}

type Density = "LOW" | "MID" | "HIGH" | "UNKNOWN";

const LEVEL_META: Record<
  Density,
  {
    fill: string;
    dot: string;
    label: string;
  }
> = {
  LOW: {
    fill: "#BFF2C9",
    dot: "#52C96B",
    label: "원활",
  },
  MID: {
    fill: "#F8E694",
    dot: "#F2BE33",
    label: "보통",
  },
  HIGH: {
    fill: "#F6B8B8",
    dot: "#F36A76",
    label: "혼잡",
  },
  UNKNOWN: {
    fill: "#DDE5EF",
    dot: "#94A3B8",
    label: "확인 필요",
  },
};

function toDensity(hall?: Hall): Density {
  if (!hall) return "UNKNOWN";

  if (hall.operationStatus === "CHECK_REQUIRED") {
    return "UNKNOWN";
  }

  const raw = String(hall.level ?? "")
    .trim()
    .toUpperCase();

  if (["1", "2", "LOW", "RELAXED", "SPACIOUS", "FREE", "원활", "여유"].includes(raw)) {
    return "LOW";
  }

  if (["3", "MID", "MEDIUM", "NORMAL", "MODERATE", "보통"].includes(raw)) {
    return "MID";
  }

  if (["4", "5", "HIGH", "BUSY", "CROWDED", "VERY_CROWDED", "혼잡", "매우혼잡"].includes(raw)) {
    return "HIGH";
  }

  return "UNKNOWN";
}

function getHallNumber(hall: Hall): string | null {
  const name = String(hall.name ?? "");
  const id = String(hall.id ?? "");

  const match =
    name.match(/(\d+)\s*번?\s*출국장/) ??
    name.match(/출국장\s*(\d+)/) ??
    id.match(/^(?:H|HALL)?0*(\d+)$/i);

  return match?.[1] ?? null;
}

function getHallByNumber(halls: Hall[], number: string) {
  return halls.find((hall) => getHallNumber(hall) === number);
}

interface Zone {
  number: string;
  hall?: Hall;
  density: Density;
  selected: boolean;
  x: number;
  y: number;
  w: number;
  h: number;
}

function makeZones(terminal: Terminal, halls: Hall[], selectedId: string | null): Zone[] {
  const numbers = terminal === "T1" ? ["1", "2", "3", "4", "5", "6"] : ["1", "2"];

  if (terminal === "T2") {
    const zonesT2 = [
      { number: "1", x: 255, y: 207, w: 190, h: 78 },
      { number: "2", x: 455, y: 207, w: 190, h: 78 },
    ];

    return zonesT2.map((base) => {
      const hall = getHallByNumber(halls, base.number);
      return {
        ...base,
        hall,
        density: toDensity(hall),
        selected: hall?.id === selectedId,
      };
    });
  }

  const zonesT1 = [
    { number: "1", x: 120, y: 205, w: 120, h: 84 },
    { number: "2", x: 242, y: 197, w: 120, h: 88 },
    { number: "3", x: 364, y: 190, w: 120, h: 92 },
    { number: "4", x: 486, y: 190, w: 120, h: 92 },
    { number: "5", x: 608, y: 197, w: 120, h: 88 },
    { number: "6", x: 730, y: 205, w: 120, h: 84 },
  ];

  return zonesT1.map((base) => {
    const hall = getHallByNumber(halls, base.number);
    return {
      ...base,
      hall,
      density: toDensity(hall),
      selected: hall?.id === selectedId,
    };
  });
}

function Person({
  x,
  y,
  scale = 1,
  body = "#4D7096",
}: {
  x: number;
  y: number;
  scale?: number;
  body?: string;
}) {
  return (
    <g transform={`translate(${x} ${y}) scale(${scale})`} className="iso-person">
      <ellipse cx="0" cy="2.8" rx="4.2" ry="1.8" fill="#2D4361" opacity="0.14" />
      <path d="M-2.2 0 L-3.1 6.6 M2.2 0 L3.1 6.6" stroke="#465A71" strokeWidth="1.8" strokeLinecap="round" />
      <path d="M-3.5 -8.5 L3.5 -8.5 L4.2 0 L-4.2 0 Z" fill={body} />
      <path d="M-3.4 -6.8 L-6.2 -1.4 M3.4 -6.8 L6.2 -1.4" stroke={body} strokeWidth="1.8" strokeLinecap="round" />
      <circle cx="0" cy="-11.5" r="3.1" fill="#E9B895" />
      <path d="M-2.8 -12.4 Q0 -16 2.8 -12.4" fill="#334B64" />
    </g>
  );
}

function QueuePost({ x, y, h = 26 }: { x: number; y: number; h?: number }) {
  return (
    <g className="iso-queue-post">
      <line x1={x} y1={y} x2={x} y2={y - h} stroke="#3C536B" strokeWidth="2" />
      <circle cx={x} cy={y - h} r="2.3" fill="#314960" />
      <circle cx={x} cy={y} r="2.3" fill="#314960" />
    </g>
  );
}

function QueueLine({
  x1,
  y1,
  x2,
  y2,
}: {
  x1: number;
  y1: number;
  x2: number;
  y2: number;
}) {
  return (
    <line
      x1={x1}
      y1={y1}
      x2={x2}
      y2={y2}
      stroke="#314A63"
      strokeWidth="1.6"
      opacity="0.7"
    />
  );
}

function MiniPlant({ x, y, scale = 1 }: { x: number; y: number; scale?: number }) {
  return (
    <g transform={`translate(${x} ${y}) scale(${scale})`}>
      <rect x="-6" y="0" width="12" height="7" rx="1.5" fill="#C7D2E3" stroke="#A9B9CF" strokeWidth="1" />
      <ellipse cx="-3" cy="-5" rx="4.2" ry="6.2" fill="#74C16F" />
      <ellipse cx="3" cy="-6" rx="4.2" ry="6.8" fill="#6AB96A" />
      <ellipse cx="0" cy="-10" rx="4.4" ry="7.6" fill="#8AD284" />
    </g>
  );
}

function ZonePeople({ zone }: { zone: Zone }) {
  const positions =
    zone.density === "HIGH"
      ? [
          [0.16, 0.72], [0.24, 0.62], [0.30, 0.78], [0.39, 0.60], [0.46, 0.72],
          [0.54, 0.58], [0.61, 0.76], [0.68, 0.66], [0.76, 0.82], [0.84, 0.70],
          [0.22, 0.44], [0.34, 0.42], [0.49, 0.45], [0.64, 0.43], [0.78, 0.48],
        ]
      : zone.density === "MID"
        ? [
            [0.20, 0.74], [0.33, 0.66], [0.48, 0.76], [0.62, 0.62], [0.76, 0.76],
            [0.28, 0.46], [0.56, 0.46], [0.80, 0.48],
          ]
        : zone.density === "LOW"
          ? [
              [0.24, 0.74], [0.54, 0.66], [0.79, 0.74], [0.42, 0.48],
            ]
          : [];

  const colors = ["#3F6893", "#F09C62", "#6C89B2", "#4FA78F", "#7B5FB6"];

  return (
    <g pointerEvents="none">
      {positions.map(([ux, uy], index) => (
        <Person
          key={index}
          x={zone.x + zone.w * ux}
          y={zone.y + zone.h * uy}
          scale={0.82}
          body={colors[index % colors.length]}
        />
      ))}
    </g>
  );
}

function HallLabel({
  zone,
  onSelect,
}: {
  zone: Zone;
  onSelect: (id: string) => void;
}) {
  const meta = LEVEL_META[zone.density];
  const labelW = 102;
  const labelH = 52;
  const labelX = zone.x + zone.w / 2 - labelW / 2;
  const labelY =
    zone.number === "1" || zone.number === "6"
      ? zone.y - 70
      : zone.number === "2" || zone.number === "5"
        ? zone.y - 84
        : zone.y - 96;

  const anchorX = zone.x + zone.w / 2;
  const anchorY = zone.y + 6;

  const clickable = Boolean(zone.hall);

  return (
    <g
      className={[
        "iso-hall-label",
        clickable ? "is-clickable" : "",
        zone.selected ? "is-selected" : "",
      ].join(" ")}
      role={clickable ? "button" : undefined}
      tabIndex={clickable ? 0 : undefined}
      aria-label={`${zone.number}번 출국장`}
      onClick={() => {
        if (zone.hall) onSelect(zone.hall.id);
      }}
      onKeyDown={(e) => {
        if (!zone.hall) return;
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          onSelect(zone.hall.id);
        }
      }}
    >
      <line
        x1={anchorX}
        y1={anchorY}
        x2={anchorX}
        y2={labelY + labelH}
        stroke="#E8EDF5"
        strokeWidth="5"
        strokeLinecap="round"
      />
      <line
        x1={anchorX}
        y1={anchorY}
        x2={anchorX}
        y2={labelY + labelH}
        stroke="#D9E0EC"
        strokeWidth="1.5"
        strokeLinecap="round"
      />
      <circle cx={anchorX} cy={anchorY} r="4" fill="#F6F9FD" stroke="#E0E7F2" />
      <rect
        x={labelX}
        y={labelY}
        width={labelW}
        height={labelH}
        rx="12"
        fill="#FFFFFF"
        stroke={zone.selected ? "#2A65D7" : "#E7EBF4"}
        strokeWidth={zone.selected ? 2.2 : 1.2}
        filter="url(#label-shadow)"
      />
      <text
        x={anchorX}
        y={labelY + 19}
        textAnchor="middle"
        className="iso-label-title"
      >
        {zone.number}번 출국장
      </text>
      <circle cx={anchorX - 18} cy={labelY + 35} r="6.4" fill={meta.dot} />
      <text
        x={anchorX + 8}
        y={labelY + 40}
        textAnchor="middle"
        className="iso-label-status"
      >
        {meta.label}
      </text>
    </g>
  );
}

function Legend() {
  return (
    <div className="iso-legend">
      <span><i className="iso-dot iso-dot--low" />원활</span>
      <span><i className="iso-dot iso-dot--mid" />보통</span>
      <span><i className="iso-dot iso-dot--high" />혼잡</span>
    </div>
  );
}

export default function TerminalMap({
  terminal,
  halls,
  selectedId,
  onSelect,
}: Props) {
  const uid = useId().replace(/:/g, "");
  const clipId = `clip-${uid}`;
  const zones = useMemo(() => makeZones(terminal, halls, selectedId), [terminal, halls, selectedId]);

  const selectedHall = halls.find((hall) => hall.id === selectedId);

  return (
    <div className="terminal3d">
      <div className="terminal3d-stage">
        <Legend />

        {selectedHall && (
          <div className="iso-selection">
            <strong>{selectedHall.name}</strong>
            <span>
              {selectedHall.operationStatus === "CHECK_REQUIRED"
                ? "운영 확인 필요"
                : LEVEL_META[toDensity(selectedHall)].label}
            </span>
            <span>
              {selectedHall.currentCount == null
                ? "인원 확인 중"
                : `${selectedHall.currentCount.toLocaleString()}명`}
            </span>
          </div>
        )}

        <svg
          className="iso-svg"
          viewBox="0 0 980 560"
          preserveAspectRatio="xMidYMid meet"
          role="img"
          aria-label={`${terminal} 출국장 아이소메트릭 혼잡도 지도`}
        >
          <defs>
            <linearGradient id="bg-grad" x1="0" y1="0" x2="1" y2="1">
              <stop offset="0%" stopColor="#F7FAFE" />
              <stop offset="100%" stopColor="#EEF3FA" />
            </linearGradient>

            <linearGradient id="glass-grad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#D7EEFF" />
              <stop offset="100%" stopColor="#B7D7F0" />
            </linearGradient>

            <linearGradient id="roof-grad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#EEF4FB" />
              <stop offset="100%" stopColor="#D9E6F4" />
            </linearGradient>

            <linearGradient id="wall-grad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#FDFEFF" />
              <stop offset="100%" stopColor="#D9E4F0" />
            </linearGradient>

            <linearGradient id="floor-grad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#F8FBFF" />
              <stop offset="100%" stopColor="#DFE7F2" />
            </linearGradient>

            <linearGradient id="blue-sign" x1="0" y1="0" x2="1" y2="1">
              <stop offset="0%" stopColor="#3C79D2" />
              <stop offset="100%" stopColor="#1E488E" />
            </linearGradient>

            <filter id="label-shadow" x="-30%" y="-30%" width="160%" height="180%">
              <feDropShadow dx="0" dy="6" stdDeviation="6" floodColor="#7487A4" floodOpacity="0.18" />
            </filter>

            <filter id="soft-shadow" x="-20%" y="-20%" width="160%" height="160%">
              <feDropShadow dx="0" dy="6" stdDeviation="8" floodColor="#8BA0BD" floodOpacity="0.18" />
            </filter>

            <clipPath id={clipId}>
              <rect x="0" y="0" width="980" height="560" rx="18" />
            </clipPath>
          </defs>

          <g clipPath={`url(#${clipId})`}>
            <rect x="0" y="0" width="980" height="560" fill="url(#bg-grad)" />

            {/* 메인 그림자 */}
            <ellipse cx="490" cy="470" rx="355" ry="46" fill="#B9C6D7" opacity="0.22" />

            {/* 상단 출국장 백 플랫폼 */}
            <path
              d="
                M120 210
                Q490 128 860 210
                L820 320
                Q490 278 160 320
                Z
              "
              fill="url(#roof-grad)"
              stroke="#C8D7E8"
              strokeWidth="2"
              filter="url(#soft-shadow)"
            />

            {/* 상단 외벽 / 유리 */}
            <path
              d="
                M142 198
                Q490 122 838 198
                L814 244
                Q490 180 166 244
                Z
              "
              fill="url(#glass-grad)"
              opacity="0.9"
              stroke="#AFC8E1"
              strokeWidth="1.5"
            />

            {/* 세로 프레임 */}
            {Array.from({ length: 17 }).map((_, i) => {
              const x = 165 + i * 39;
              const topY = 193 - Math.abs(8 - i) * 1.5;
              const bottomY = 244 - Math.abs(8 - i) * 0.4;
              return (
                <line
                  key={i}
                  x1={x}
                  y1={topY}
                  x2={x}
                  y2={bottomY}
                  stroke="#8DB0CF"
                  strokeWidth="2"
                  opacity="0.78"
                />
              );
            })}

            {/* 상단 혼잡 구역 */}
            {zones.map((zone) => (
              <g key={zone.number} className={zone.selected ? "zone-selected" : ""}>
                <path
                  d={`
                    M${zone.x} ${zone.y}
                    L${zone.x + zone.w} ${zone.y}
                    L${zone.x + zone.w - 14} ${zone.y + zone.h}
                    L${zone.x + 14} ${zone.y + zone.h}
                    Z
                  `}
                  fill={LEVEL_META[zone.density].fill}
                  stroke="#F6FAFD"
                  strokeWidth={zone.selected ? 3.4 : 2.4}
                  className="iso-zone-surface"
                />

                {/* 내부 라인 */}
                <line
                  x1={zone.x + zone.w / 2}
                  y1={zone.y}
                  x2={zone.x + zone.w / 2}
                  y2={zone.y + zone.h}
                  stroke="#FFFFFF"
                  strokeWidth="1"
                  opacity="0.48"
                />
                <line
                  x1={zone.x + zone.w * 0.25}
                  y1={zone.y}
                  x2={zone.x + zone.w * 0.25 + 6}
                  y2={zone.y + zone.h}
                  stroke="#FFFFFF"
                  strokeWidth="1"
                  opacity="0.28"
                />
                <line
                  x1={zone.x + zone.w * 0.75}
                  y1={zone.y}
                  x2={zone.x + zone.w * 0.75 - 6}
                  y2={zone.y + zone.h}
                  stroke="#FFFFFF"
                  strokeWidth="1"
                  opacity="0.28"
                />

                {/* 선택 클릭 영역 */}
                {zone.hall && (
                  <path
                    d={`
                      M${zone.x} ${zone.y}
                      L${zone.x + zone.w} ${zone.y}
                      L${zone.x + zone.w - 14} ${zone.y + zone.h}
                      L${zone.x + 14} ${zone.y + zone.h}
                      Z
                    `}
                    fill="transparent"
                    className="iso-zone-hit"
                    onClick={() => onSelect(zone.hall!.id)}
                  />
                )}

                <ZonePeople zone={zone} />
              </g>
            ))}

            {/* 좌우 경사 기둥 */}
            <path d="M132 193 L110 212 L110 324 L128 312 Z" fill="#DCE6F2" stroke="#C5D4E4" />
            <path d="M848 193 L870 212 L870 324 L852 312 Z" fill="#DCE6F2" stroke="#C5D4E4" />

            {/* 하단 메인 홀 */}
            <path
              d="
                M145 330
                Q490 284 835 330
                L835 456
                Q490 494 145 456
                Z
              "
              fill="url(#wall-grad)"
              stroke="#CBD8E7"
              strokeWidth="2"
            />

            {/* 전면 바닥 */}
            <path
              d="
                M95 375
                Q490 332 885 375
                L838 470
                Q490 528 142 470
                Z
              "
              fill="url(#floor-grad)"
              stroke="#D2DCE8"
              strokeWidth="2"
            />

            {/* 전면 유리 난간 */}
            <path
              d="
                M140 470
                Q490 528 838 470
                L830 486
                Q490 543 148 486
                Z
              "
              fill="#D6EDF9"
              stroke="#B8D6EB"
              strokeWidth="1.5"
            />

            {/* 전면 하단 건물 */}
            <path
              d="
                M182 468
                Q490 510 798 468
                L798 530
                Q490 562 182 530
                Z
              "
              fill="#EAF2FA"
              stroke="#CDDBEA"
              strokeWidth="1.5"
            />

            {/* 하단 전면 창 프레임 */}
            {Array.from({ length: 15 }).map((_, i) => {
              const x = 232 + i * 36;
              return (
                <g key={i}>
                  <line x1={x} y1={485} x2={x} y2={529} stroke="#A9C6DD" strokeWidth="1.7" />
                </g>
              );
            })}
            <line x1="215" y1="503" x2="765" y2="503" stroke="#A9C6DD" strokeWidth="1.2" />
            <line x1="215" y1="518" x2="765" y2="518" stroke="#A9C6DD" strokeWidth="1.2" />

            {/* 체크인 */}
            <g transform="translate(175 362)">
              <path d="M0 35 L145 43 L165 24 L20 16 Z" fill="#CEDBED" stroke="#AFC4DB" />
              <path d="M0 35 L145 43 L145 66 L0 58 Z" fill="#EDF4FB" stroke="#B7C9DE" />
              <path d="M145 43 L165 24 L165 47 L145 66 Z" fill="#C3D3E5" stroke="#AFC4DB" />

              <rect x="33" y="-2" width="80" height="28" rx="6" fill="url(#blue-sign)" />
              <text x="73" y="16" textAnchor="middle" fill="#FFFFFF" fontSize="12" fontWeight="800">
                체크인
              </text>

              {Array.from({ length: 4 }).map((_, i) => (
                <g key={i} transform={`translate(${18 + i * 30} 41)`}>
                  <rect x="0" y="0" width="22" height="11" rx="1" fill="#FDFEFF" stroke="#B8CADC" />
                  <rect x="2" y="2" width="18" height="3.8" fill="#4A90E2" />
                </g>
              ))}

              <Person x={18} y={43} scale={0.72} body="#6A8CB2" />
              <Person x={63} y={43} scale={0.72} body="#F0A56D" />
              <Person x={108} y={43} scale={0.72} body="#6A8CB2" />
            </g>

            {/* 보안검색 */}
            <g transform="translate(494 354)">
              <rect x="0" y="0" width="102" height="24" rx="6" fill="url(#blue-sign)" />
              <text x="51" y="16" textAnchor="middle" fill="#FFFFFF" fontSize="12" fontWeight="800">
                보안검색
              </text>

              {Array.from({ length: 3 }).map((_, i) => (
                <g key={i} transform={`translate(${15 + i * 24} 31)`}>
                  <rect x="0" y="0" width="14" height="28" fill="#EEF5FC" stroke="#A8BED4" />
                  <rect x="4" y="6" width="6" height="16" fill="#C1D8EE" />
                </g>
              ))}

              {Array.from({ length: 5 }).map((_, i) => {
                const x = 8 + i * 20;
                return (
                  <g key={i}>
                    <QueuePost x={x} y={79} h={24} />
                    <QueuePost x={x} y={109} h={24} />
                    <QueueLine x1={x} y1={55} x2={x} y2={85} />
                    <QueueLine x1={x} y1={85} x2={x + 18} y2={85} />
                    <QueueLine x1={x} y1={115} x2={x + 18} y2={115} />
                  </g>
                );
              })}
            </g>

            {/* 전광판 */}
            <g transform="translate(748 360)">
              <path d="M0 24 L62 32 L62 -28 L0 -36 Z" fill="url(#blue-sign)" stroke="#224E97" />
              <text x="19" y="-8" fill="#FFFFFF" fontSize="13" fontWeight="800">✈</text>
              {Array.from({ length: 4 }).map((_, i) => (
                <g key={i}>
                  <rect x="20" y={-15 + i * 10} width="8" height="2.3" fill="#FFD857" />
                  <rect x="32" y={-15 + i * 10} width="18" height="2.3" fill="#D7E7F9" />
                </g>
              ))}
            </g>

            {/* 출국장 표지판 */}
            <g transform="translate(865 330)">
              <path d="M0 0 L45 10 L45 165 L0 155 Z" fill="url(#blue-sign)" stroke="#224E97" />
              <text x="22" y="34" textAnchor="middle" fill="#FFFFFF" fontSize="15" fontWeight="800">✈</text>
              <text x="22" y="74" textAnchor="middle" fill="#FFFFFF" fontSize="18" fontWeight="800">
                출국장
              </text>
              <text x="22" y="91" textAnchor="middle" fill="#D9EBFF" fontSize="10" fontWeight="700">
                Departures
              </text>
              <text x="22" y="120" textAnchor="middle" fill="#FFFFFF" fontSize="22" fontWeight="800">
                →
              </text>
            </g>

            {/* ICN 로고 */}
            <text
              x="720"
              y="505"
              textAnchor="middle"
              fill="#FFFFFF"
              fontSize="28"
              fontStyle="italic"
              fontWeight="800"
              opacity="0.92"
            >
              ICN
            </text>

            {/* 식물 */}
            <MiniPlant x={195} y={331} scale={1.08} />
            <MiniPlant x={780} y={335} scale={1.08} />
            <MiniPlant x={705} y={392} scale={0.95} />
            <MiniPlant x={460} y={388} scale={0.82} />

            {/* 홀 내부 사람 */}
            <Person x={365} y={431} scale={0.94} body="#567CA7" />
            <Person x={435} y={404} scale={0.88} body="#F0A46C" />
            <Person x={490} y={426} scale={0.92} body="#AA7AB7" />
            <Person x={608} y={404} scale={0.84} body="#49A18D" />
            <Person x={315} y={478} scale={0.88} body="#567CA7" />
            <Person x={690} y={444} scale={0.88} body="#F0A46C" />
            <Person x={575} y={472} scale={0.86} body="#567CA7" />
            <Person x={748} y={428} scale={0.84} body="#567CA7" />

            {/* DEPARTURE HALL 간판 */}
            <g transform="translate(387 112)">
              <rect x="0" y="0" width="206" height="34" rx="8" fill="url(#blue-sign)" />
              <text x="103" y="22" textAnchor="middle" fill="#FFFFFF" fontSize="15" fontWeight="800">
                DEPARTURE HALL
              </text>
            </g>

            {/* 출국장 라벨 */}
            {zones.map((zone) => (
              <HallLabel key={zone.number} zone={zone} onSelect={onSelect} />
            ))}
          </g>
        </svg>
      </div>

      <div className="terminal3d-footer">
        <span>{terminal} · 3F 출발층</span>
        <span>아이소메트릭 혼잡도 개략도</span>
      </div>
    </div>
  );
}