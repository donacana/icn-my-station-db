
import { useEffect, useMemo, useState } from 'react';
import { getFlights, type Flight } from '../api/client';
import { useLiveUpdates } from '../hooks/useLiveUpdates';
import 'flag-icons/css/flag-icons.min.css';
import './FlightsPage.css';

type Terminal = 'T1' | 'T2';

type FlightExtra = Flight & {
  airlineCode?: string | null;
  countryCode?: string | null;
};

const AIRLINES: Record<string, { name: string; domain: string }> = {
  KE: { name: '대한항공', domain: 'koreanair.com' },
  OZ: { name: '아시아나항공', domain: 'flyasiana.com' },
  '7C': { name: '제주항공', domain: 'jejuair.net' },
  TW: { name: '티웨이항공', domain: 'twayair.com' },
  LJ: { name: '진에어', domain: 'jinair.com' },
  BX: { name: '에어부산', domain: 'airbusan.com' },
  RS: { name: '에어서울', domain: 'flyairseoul.com' },
  ZE: { name: '이스타항공', domain: 'eastarjet.com' },
  DL: { name: '델타항공', domain: 'delta.com' },
  UA: { name: '유나이티드항공', domain: 'united.com' },
  JL: { name: '일본항공', domain: 'jal.co.jp' },
  NH: { name: '전일본공수', domain: 'ana.co.jp' },
  SQ: { name: '싱가포르항공', domain: 'singaporeair.com' },
  CX: { name: '캐세이퍼시픽', domain: 'cathaypacific.com' },
  QR: { name: '카타르항공', domain: 'qatarairways.com' },
  EK: { name: '에미레이트항공', domain: 'emirates.com' },
  KL: { name: 'KLM', domain: 'klm.com' },
};

const COUNTRY_BY_AIRPORT: Record<string, string> = {
  NRT: 'JP', HND: 'JP', KIX: 'JP', FUK: 'JP',
  CTS: 'JP', NGO: 'JP', OKA: 'JP',
  PVG: 'CN', PEK: 'CN', PKX: 'CN',
  SHA: 'CN', CAN: 'CN', TAO: 'CN',
  TPE: 'TW', TSA: 'TW', KHH: 'TW',
  HKG: 'HK', MFM: 'MO',
  BKK: 'TH', DMK: 'TH', HKT: 'TH',
  SGN: 'VN', HAN: 'VN', DAD: 'VN',
  MNL: 'PH', CEB: 'PH', CRK: 'PH',
  SIN: 'SG', KUL: 'MY', CGK: 'ID',
  DPS: 'ID', DEL: 'IN',
  LAX: 'US', SFO: 'US', SEA: 'US',
  JFK: 'US', EWR: 'US', ORD: 'US',
  ATL: 'US', DFW: 'US', HNL: 'US',
  YVR: 'CA', YYZ: 'CA',
  LHR: 'GB', CDG: 'FR', FRA: 'DE',
  MUC: 'DE', FCO: 'IT', AMS: 'NL',
  SYD: 'AU', MEL: 'AU',
  DXB: 'AE', DOH: 'QA',
};

function flightTime(value: string | null | undefined) {
  if (!value) return '—';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '—';

  return date.toLocaleTimeString('ko-KR', {
    timeZone: 'Asia/Seoul',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  });
}

function observationTime(date: Date) {
  return date.toLocaleString('ko-KR', {
    timeZone: 'Asia/Seoul',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  });
}

function airlineCode(flight: FlightExtra) {
  const explicit = flight.airlineCode?.trim().toUpperCase();
  if (explicit) return explicit;

  return (
    flight.flightNo.trim().toUpperCase()
      .match(/^[A-Z0-9]{2}/)?.[0] ?? ''
  );
}

function countryCode(flight: FlightExtra) {
  const explicit = flight.countryCode?.trim().toUpperCase();

  if (explicit && /^[A-Z]{2}$/.test(explicit)) {
    return explicit;
  }

  return COUNTRY_BY_AIRPORT[
    flight.airportCode?.trim().toUpperCase() ?? ''
  ] ?? '';
}

function CountryFlag({ code }: { code: string }) {
  if (!/^[A-Z]{2}$/.test(code)) {
    return <span aria-label="국가 정보 없음">🌐</span>;
  }

  return (
    <span
      className={`fi fi-${code.toLowerCase()}`}
      role="img"
      aria-label={`${code} 국기`}
    />
  );
}

function statusLabel(value: string) {
  const status = (value ?? '').toUpperCase();

  if (status.includes('DELAY') || status.includes('지연')) {
    return '지연';
  }
  if (status.includes('CANCEL') || status.includes('결항')) {
    return '결항';
  }
  if (status.includes('BOARD') || status.includes('탑승')) {
    return '탑승중';
  }
  if (status.includes('DEPART') || status.includes('출발')) {
    return '출발';
  }
  if (status.includes('ARRIV') || status.includes('도착')) {
    return '도착';
  }
  if (
    status.includes('SCHEDULE') ||
    status.includes('ON_TIME') ||
    status.includes('정상') ||
    status.includes('예정')
  ) {
    return '정상';
  }

  return value || '정보 없음';
}

function statusClass(flight: FlightExtra) {
  const status = statusLabel(flight.status);

  if (flight.delayMinutes > 0 || status === '지연') {
    return 'delay';
  }
  if (status === '결항') return 'cancel';
  if (status === '탑승중') return 'boarding';

  return 'normal';
}

function getDepartureTime(flight: FlightExtra) {
  const estimated = flight.estimatedAt
    ? Date.parse(flight.estimatedAt)
    : NaN;

  if (Number.isFinite(estimated)) return estimated;
  return Date.parse(flight.scheduledAt);
}

function AirlineMark({ flight }: { flight: FlightExtra }) {
  const code = airlineCode(flight);
  const brand = AIRLINES[code];
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    setFailed(false);
  }, [code]);

  return (
    <span className="icn-flight-airline-mark">
      {brand && !failed ? (
        <img
          src={
            `https://www.google.com/s2/favicons?domain=` +
            `${encodeURIComponent(brand.domain)}&sz=64`
          }
          alt=""
          loading="lazy"
          onError={() => setFailed(true)}
        />
      ) : (
        <span>{code || '✈'}</span>
      )}
    </span>
  );
}

function GateTimeline({
  terminal,
  flights,
  now,
}: {
  terminal: Terminal;
  flights: FlightExtra[];
  now: Date;
}) {
  const MINUTE = 60 * 1000;
  const HOUR = 60 * MINUTE;
  const currentTime = now.getTime();
  // 메인 운행현황과 동일하게 예정/변경 시간 모두 고려합니다.
  // 좌우 터미널은 동일한 현재 시각 기준 시간축을 공유합니다.
  const start = Math.floor((currentTime - HOUR) / (30 * MINUTE)) * (30 * MINUTE);
  const end = start + 4 * HOUR;
  const duration = end - start;
  const parseTime = (value: string | null | undefined) => {
    const parsed = value ? Date.parse(value) : NaN;
    return Number.isFinite(parsed) ? parsed : null;
  };
  const toPercent = (time: number) =>
    Math.max(0, Math.min(100, ((time - start) / duration) * 100));
  const isDelayed = (flight: FlightExtra) => {
    const state = String(flight.status ?? '').toUpperCase();
    return state.includes('DELAY') || state.includes('지연') ||
      Number(flight.delayMinutes ?? 0) > 0;
  };

  const gateFlights = useMemo(() => {
    const candidates = flights.filter(flight => {
      const scheduled = parseTime(flight.scheduledAt);
      const estimated = parseTime(flight.estimatedAt);
      const display = estimated ?? scheduled;
      return (
        flight.terminal?.toUpperCase() === terminal &&
        Boolean(String(flight.gate ?? '').trim()) &&
        display !== null &&
        display >= start &&
        display <= end &&
        statusLabel(flight.status) !== '결항'
      );
    });

    const gates = new Map<string, FlightExtra[]>();
    for (const flight of candidates) {
      const gate = String(flight.gate).replace(/^G/i, '').trim();
      if (!gates.has(gate)) gates.set(gate, []);
      gates.get(gate)?.push(flight);
    }

    const proximity = (items: FlightExtra[]) =>
      Math.min(...items.map(flight => {
        const display = parseTime(flight.estimatedAt) ??
          parseTime(flight.scheduledAt) ?? currentTime;
        return Math.abs(display - currentTime);
      }));

    return [...gates.entries()]
      .sort((a, b) => proximity(a[1]) - proximity(b[1]))
      .slice(0, 4)
      .map(([gate, items]) => [
        gate,
        [...items].sort((a, b) =>
          (parseTime(a.estimatedAt) ?? parseTime(a.scheduledAt) ?? 0) -
          (parseTime(b.estimatedAt) ?? parseTime(b.scheduledAt) ?? 0)),
      ] as const);
  }, [flights, terminal, start, end, currentTime]);

  const ticks = Array.from({ length: 5 }, (_, i) =>
    new Date(start + i * HOUR).toLocaleTimeString('ko-KR', {
      timeZone: 'Asia/Seoul',
      hour: '2-digit',
      minute: '2-digit',
      hour12: false,
    })
  );

  return (
    <article className="icn-flight-card icn-flight-terminal-card">
      <div className="icn-flight-card-head">
        <h2>
          <span className="icn-flight-terminal-icon">
            {terminal === 'T1' ? '1' : '2'}
          </span>
          제{terminal === 'T1' ? '1' : '2'}여객터미널
          <small>{terminal}</small>
        </h2>

        <span className="icn-flight-pill">게이트 일정</span>
      </div>

      <div className="icn-flight-timeline">
        <div className="icn-flight-ticks">
          {ticks.map((tick, index) => (
            <span key={`${tick}-${index}`}>{tick}</span>
          ))}
        </div>

        <div className="icn-flight-gate-list">
          {gateFlights.length > 0 ? (
            gateFlights.map(([gate, items]) => {
              // 같은 게이트에서 시간 위치가 가까운 항공편은 서로 다른 층에 배치
              // 위치 계산은 컨테이너 폭과 무관하게 동일한 시간 비율을 사용
              const laneEnds: number[] = [];
              const placed = items.map(flight => {
                const display = parseTime(flight.estimatedAt) ??
                  parseTime(flight.scheduledAt) ?? start;
                const position = toPercent(display);
                const lane = laneEnds.findIndex(last => position - last >= 19);
                const chosenLane = lane < 0 ? laneEnds.length : lane;
                laneEnds[chosenLane] = position;
                return { flight, lane: chosenLane };
              });
              const rowHeight = Math.max(29, laneEnds.length * 32 + 4);
              return (
              <div className="icn-flight-gate-row" key={gate} style={{ minHeight: rowHeight }}>
                <span className="icn-flight-gate-name">
                  G{gate}
                </span>

                <div className="icn-flight-track" style={{ height: rowHeight }}>
                  {placed.map(({ flight, lane }, index) => {
                    const scheduled = parseTime(flight.scheduledAt);
                    const estimated = parseTime(flight.estimatedAt);
                    const display = estimated ?? scheduled;
                    if (display === null) return null;
                    const delayed = isDelayed(flight);
                    const delayMinutes = Number(flight.delayMinutes ?? 0);
                    const title = [
                      flight.flightNo,
                      `예정 ${flightTime(flight.scheduledAt)}`,
                      `변경 ${flightTime(flight.estimatedAt)}`,
                      statusLabel(flight.status),
                      delayed && delayMinutes > 0 ? `지연 +${delayMinutes}분` : '',
                    ].filter(Boolean).join(' | ');

                    return (
                      <div key={`${flight.flightNo}-${index}`}>
                        {delayed && scheduled !== null &&
                          scheduled >= start && scheduled <= end && (
                          <div
                            title={`기존 예정 ${flightTime(flight.scheduledAt)}`}
                            style={{
                              position: 'absolute',
                              left: `clamp(40px, ${toPercent(scheduled)}%, calc(100% - 40px))`,
                              top: 4 + lane * 32,
                              transform: 'translateX(-50%)',
                              width: 80,
                              height: 28,
                              border: '1.5px dashed #94a3b8',
                              borderRadius: 5,
                              pointerEvents: 'none',
                            }}
                          />
                        )}
                        <div
                          className={`icn-flight-bar ${delayed ? 'delay' : 'normal'}`}
                          style={{
                            left: `clamp(40px, ${toPercent(display)}%, calc(100% - 40px))`,
                            width: 80,
                            maxWidth: 'none',
                            transform: 'translateX(-50%)',
                            top: 6 + lane * 32,
                          }}
                          title={title}
                          aria-label={title}
                        >
                          {flight.flightNo}
                          {delayed && delayMinutes > 0 ? ` +${delayMinutes}분` : ''}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
              );
            })
          ) : (
            <div className="icn-flight-empty-gates">
              해당 시간대의 게이트 정보가 없습니다.
            </div>
          )}
          {gateFlights.length > 0 && currentTime >= start && currentTime <= end && (
            <div
              className="icn-flight-current-time-line"
              style={{
                left: `calc(var(--gate-label-offset) + (100% - var(--gate-label-offset)) * ${(currentTime - start) / duration})`,
              }}
              aria-label={`현재 시각 ${now.toLocaleTimeString('ko-KR', { timeZone: 'Asia/Seoul', hour: '2-digit', minute: '2-digit', hour12: false })}`}
              title="현재 시각"
            />
          )}
        </div>
      </div>

      <p className="icn-flight-timeline-note">
        현재 시각 기준 · 터미널별 최대 4개 게이트 · 동일 게이트의 항공편 모두 표시
      </p>
    </article>
  );
}

export default function FlightsPage() {
  const [terminal, setTerminal] = useState('ALL');
  const [status, setStatus] = useState('ALL');
  const [search, setSearch] = useState('');
  const [now, setNow] = useState(() => new Date());
  const [page, setPage] = useState(1);
  const [pageInitialized, setPageInitialized] = useState(false);
  const PAGE_SIZE = 20;

  useEffect(() => {
    const timer = window.setInterval(() => {
      setNow(new Date());
    }, 60_000);

    return () => window.clearInterval(timer);
  }, []);

  // 최초 REST 조회 후 WebSocket으로 출발편 자동 갱신
  const api = useLiveUpdates<Flight[]>({
    topic: 'flights',
    scope: 'DEPARTURE',
    fetcher: signal => getFlights('DEPARTURE', signal),
    intervalMs: 0,
    parseMessage: value => {
      if (!Array.isArray(value)) return undefined;
      return value as Flight[];
    },
  });

  const allFlights = useMemo(
    () => (api.data ?? []) as FlightExtra[],
    [api.data]
  );

  const filteredFlights = useMemo(() => {
    const keyword = search.trim().toLowerCase();

    return allFlights
      .filter(flight => {
        if (
          terminal !== 'ALL' &&
          flight.terminal?.toUpperCase() !== terminal
        ) {
          return false;
        }

        if (
          status !== 'ALL' &&
          statusLabel(flight.status) !== status
        ) {
          return false;
        }

        const searchable = [
          flight.flightNo,
          flight.airline,
          flight.city,
          flight.airportCode,
          airlineCode(flight),
          countryCode(flight),
        ]
          .join(' ')
          .toLowerCase();

        return searchable.includes(keyword);
      })
      .sort(
        (a, b) =>
          Date.parse(a.scheduledAt) -
          Date.parse(b.scheduledAt)
      );
  }, [allFlights, terminal, status, search]);

  const totalPages = Math.max(1, Math.ceil(filteredFlights.length / PAGE_SIZE));
  const nearestIndex = useMemo(() => {
    const current = now.getTime();
    const futureIndex = filteredFlights.findIndex(f => Date.parse(f.scheduledAt) >= current);
    return futureIndex >= 0 ? futureIndex : Math.max(0, filteredFlights.length - 1);
  }, [filteredFlights, now]);
  const nearestPage = Math.floor(nearestIndex / PAGE_SIZE) + 1;

  useEffect(() => {
    if (!api.loading && !pageInitialized) {
      setPage(nearestPage);
      setPageInitialized(true);
    }
  }, [api.loading, pageInitialized, nearestPage]);

  const visibleFlights = filteredFlights.slice(
    (Math.min(page, totalPages) - 1) * PAGE_SIZE,
    Math.min(page, totalPages) * PAGE_SIZE
  );

  const resetToNearest = () => {
    setPageInitialized(false);
  };

  const delayed = allFlights.filter(
    flight =>
      flight.delayMinutes > 0 ||
      statusLabel(flight.status) === '지연'
  ).length;

  const cancelled = allFlights.filter(
    flight => statusLabel(flight.status) === '결항'
  ).length;

  const lastScheduled = allFlights.reduce((latest, flight) => {
    const time = Date.parse(flight.scheduledAt);
    return Number.isFinite(time)
      ? Math.max(latest, time)
      : latest;
  }, 0);

  return (
    <main className="icn-detail icn-flights-page">
      {Boolean(api.error) && (
        <div className="icn-flight-error" role="alert">
          항공편 정보를 불러오지 못했습니다.
          <p>{api.error}</p>
        </div>
      )}

      <div className="icn-flight-terminal-grid">
        <GateTimeline
          terminal="T1"
          flights={allFlights}
          now={now}
        />
        <GateTimeline
          terminal="T2"
          flights={allFlights}
          now={now}
        />
      </div>

      <section className="icn-flight-card icn-flight-table-card">
        <div className="icn-flight-card-head icn-flight-table-head">
          <div>
            <h2>출발 항공편 목록</h2>
            <p className="icn-flight-count">
              조회 {allFlights.length}편 · 지연 {delayed}편 ·
              결항 {cancelled}편
            </p>
          </div>

          <div className="icn-flight-filters">
            <input
              aria-label="편명 또는 목적지 검색"
              placeholder="⌕ 편명 또는 목적지 검색"
              value={search}
              onChange={event => { setSearch(event.target.value); resetToNearest(); }}
            />

            <select
              aria-label="터미널 필터"
              value={terminal}
              onChange={event => { setTerminal(event.target.value); resetToNearest(); }}
            >
              <option value="ALL">전체 터미널</option>
              <option value="T1">T1</option>
              <option value="T2">T2</option>
            </select>

            <select
              aria-label="운항 상태 필터"
              value={status}
              onChange={event => { setStatus(event.target.value); resetToNearest(); }}
            >
              <option value="ALL">전체 상태</option>
              <option value="정상">정상</option>
              <option value="탑승중">탑승중</option>
              <option value="지연">지연</option>
              <option value="결항">결항</option>
              <option value="출발">출발</option>
            </select>
          </div>
        </div>

        {api.loading && (
          <p className="icn-flight-info">
            실제 항공편 데이터를 불러오는 중입니다.
          </p>
        )}

        <div className="icn-flight-table-scroll">
          <table>
            <thead>
              <tr>
                <th>예정 시간</th>
                <th>변경 시간</th>
                <th>편명</th>
                <th>항공사 / 목적지 국가</th>
                <th>터미널</th>
                <th>게이트</th>
                <th>운항 상태</th>
              </tr>
            </thead>

            <tbody>
              {visibleFlights.map((flight, index) => {
                const code = countryCode(flight);

                return (
                  <tr
                    key={
                      `${flight.flightNo}-` +
                      `${flight.scheduledAt}-${index}`
                    }
                  >
                    <td>{flightTime(flight.scheduledAt)}</td>
                    <td>{flightTime(flight.estimatedAt)}</td>
                    <td>
                      <strong>{flight.flightNo}</strong>
                    </td>

                    <td>
                      <div className="icn-flight-identity">
                        <span className="icn-flight-airline">
                          <AirlineMark flight={flight} />
                          <span>{flight.airline}</span>
                        </span>

                        <span className="icn-flight-divider">/</span>

                        <span className="icn-flight-destination">
                          <span
                            className="icn-flight-flag"
                            title={code || '국가 정보 없음'}
                          >
                            <CountryFlag code={code} />
                          </span>
                          <span>
                            {flight.city}
                            {flight.airportCode && (
                              <small>
                                {' '}({flight.airportCode})
                              </small>
                            )}
                          </span>
                        </span>
                      </div>
                    </td>

                    <td>{flight.terminal || '—'}</td>
                    <td>
                      {flight.gate
                        ? `G${String(flight.gate).replace(/^G/i, '')}`
                        : '—'}
                    </td>
                    <td>
                      <span
                        className={
                          `icn-flight-status ${statusClass(flight)}`
                        }
                      >
                        {statusLabel(flight.status)}
                      </span>
                    </td>
                  </tr>
                );
              })}

              {!api.loading && !api.error &&
                filteredFlights.length === 0 && (
                  <tr>
                    <td colSpan={7} className="icn-flight-empty">
                      조건에 맞는 항공편이 없습니다.
                    </td>
                  </tr>
                )}
            </tbody>
          </table>
        </div>

        {filteredFlights.length > 0 && (
          <nav className="icn-flight-pagination" aria-label="항공편 페이지 이동">
            <div className="icn-flight-pagination-top">
              <span className="icn-flight-pagination-count">총 <strong>{filteredFlights.length.toLocaleString()}</strong>편 · 페이지당 20편</span>
              <span className="icn-flight-pagination-current"><strong>{Math.min(page, totalPages)}</strong> / {totalPages} 페이지</span>
            </div>
            <div className="icn-flight-pagination-controls">
              <button className="icn-flight-page-arrow" type="button" disabled={page <= 1} onClick={() => setPage(p => Math.max(1, p - 1))} aria-label="이전 페이지">‹</button>
              <div className="icn-flight-page-numbers" aria-label="페이지 번호 목록">
                {(() => {
                  const current = Math.min(page, totalPages);
                  const start = Math.max(1, Math.min(current - 2, totalPages - 4));
                  const end = Math.min(totalPages, start + 4);
                  const pages = Array.from({ length: end - start + 1 }, (_, i) => start + i);
                  return (
                    <>
                      {start > 1 && <span className="icn-flight-page-ellipsis" aria-hidden="true">…</span>}
                      {pages.map(p => (
                        <button type="button" key={p} onClick={() => setPage(p)}
                          aria-current={p === current ? 'page' : undefined}
                          className={`icn-flight-page-number ${p === current ? 'is-active' : ''}`}>
                          {p}
                        </button>
                      ))}
                      {end < totalPages && <span className="icn-flight-page-ellipsis" aria-hidden="true">…</span>}
                    </>
                  );
                })()}
              </div>
              <button className="icn-flight-page-arrow" type="button" disabled={page >= totalPages} onClick={() => setPage(p => Math.min(totalPages, p + 1))} aria-label="다음 페이지">›</button>
            </div>

          </nav>
        )}

        <div className="icn-flight-footer">
          <span>
            실시간 운항정보 · WebSocket 자동 갱신
          </span>
          <span>
            {lastScheduled > 0
              ? `수신 데이터의 마지막 예정 시각: ${
                  observationTime(new Date(lastScheduled))
                }`
              : '마지막 예정 시각 정보 없음'}
          </span>
        </div>
      </section>
    </main>
  );
}
