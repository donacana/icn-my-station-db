// Fixed demonstration snapshot. This module is not a backend response contract.
const at = (time) => `2026-10-29T${time}:00+09:00`;
const flight = (uniqCode, flightNo, airline, city, airportCode, time, terminal, gate, status, extra = {}) => ({
  uniqCode, flightNo, airline, city, airportCode, scheduledAt: at(time),
  estimatedAt: null, terminal, gate, status, delayMinutes: 0,
  isMyFlight: false, isCodeshare: false, source: 'demo', ...extra,
});
const departures = [
  flight('demo-d1', 'KE703', '대한항공', '도쿄 · 나리타', 'NRT', '14:30', 'T2', 248, 'BOARDING'),
  flight('demo-d2', 'OZ102', '아시아나항공', '도쿄 · 나리타', 'NRT', '14:40', 'T1', 28, 'BOARDING_SOON'),
  flight('demo-d3', 'KE671', '대한항공', '쿠알라룸푸르', 'KUL', '14:50', 'T2', 251, 'DELAYED', { estimatedAt: at('15:15'), delayMinutes: 25 }),
  flight('demo-d4', '7C1104', '제주항공', '도쿄 · 나리타', 'NRT', '15:05', 'T1', 33, 'SCHEDULED'),
  flight('demo-d5', 'SQ607', '싱가포르항공', '싱가포르', 'SIN', '15:20', 'T1', 42, 'CANCELLED'),
  flight('demo-d6', 'KE915', '대한항공', '바르셀로나', 'BCN', '15:40', 'T2', 256, 'SCHEDULED'),
].map(item => ({ ...item, type: 'DEPARTURE' }));
const arrivals = [
  flight('demo-a1', 'KE704', '대한항공', '도쿄 · 나리타', 'NRT', '14:20', 'T2', 235, 'ARRIVED'),
  flight('demo-a2', 'OZ201', '아시아나항공', '로스앤젤레스', 'LAX', '14:35', 'T1', 14, 'DELAYED', { delayMinutes: 20, estimatedAt: at('14:55') }),
  flight('demo-a3', 'KE652', '대한항공', '방콕', 'BKK', '14:55', 'T2', 240, 'SCHEDULED'),
  flight('demo-a4', 'TW602', '티웨이항공', '홍콩', 'HKG', '15:10', 'T1', null, 'DIVERTED'),
].map(item => ({ ...item, type: 'ARRIVAL' }));

function statistics(flights, direction) {
  const masters = flights.filter(item => !item.isCodeshare);
  const breakdown = ['NORMAL', 'DELAYED', 'CANCELLED', 'DIVERTED'].map(category => {
    const count = masters.filter(item => {
      const group = ['DELAYED', 'CANCELLED', 'DIVERTED'].includes(item.status) ? item.status : 'NORMAL';
      return group === category;
    }).length;
    return { category, count, ratio: masters.length ? count / masters.length * 100 : 0, changeRate: null };
  });
  return { date: '2026-10-29', direction, total: masters.length, breakdown, hourly: [] };
}
const hall = (hallId, waitingCount, level, changeRate) => ({
  hallId, hallName: `${hallId}번 출국장`, waitingCount, level, changeRate, source: 'demo',
});
const facility = (facilityId, name, category, terminal, floor, location, openTime, closeTime, isOpen) => ({
  facilityId, name, category, terminal, floor, location, openTime, closeTime, isOpen,
  is24h: false, area: 'DEPARTURE', items: null, tel: null, source: 'demo',
});
export const dashboardMock = {
  source: 'demo', generatedAt: at('14:20'), myFlightNo: null,
  flights: { departures, arrivals },
  stats: { departure: statistics(departures, 'DEPARTURE'), arrival: statistics(arrivals, 'ARRIVAL') },
  congestion: {
    T1: { terminal: 'T1', measuredAt: at('14:20'), halls: [hall(1, 48, 'LOW', -12), hall(2, 186, 'HIGH', 28), hall(3, 92, 'MID', 8), hall(4, 65, 'LOW', -6), hall(5, 124, 'MID', 14), hall(6, 32, 'LOW', -18)] },
    T2: { terminal: 'T2', measuredAt: at('14:20'), halls: [hall(1, 112, 'MID', 9), hall(2, 42, 'LOW', -15)] },
  },
  alerts: [
    { alertId: 'a1', type: 'DELAY', severity: 'CRITICAL', title: 'KE671 출발 지연', message: '14:50 → 15:15 · 출발이 25분 지연되었습니다.', flightNo: 'KE671', isMine: false, isImportant: true, createdAt: at('14:18') },
    { alertId: 'a2', type: 'GATE_CHANGE', severity: 'WARN', title: 'KE703 탑승구 변경', message: '탑승구가 245번에서 248번으로 변경되었습니다.', flightNo: 'KE703', isMine: false, isImportant: true, createdAt: at('14:12') },
    { alertId: 'a3', type: 'CONGESTION', severity: 'WARN', title: 'T1 · 2번 출국장 혼잡', message: '대기인원이 증가했습니다. 다른 출국장도 확인해 보세요.', flightNo: null, isMine: false, isImportant: false, createdAt: at('14:08') },
    { alertId: 'a4', type: 'WEATHER', severity: 'INFO', title: '공항 기상 안내', message: '북서풍 4.2 m/s · 시정 10 km의 시연용 관측입니다.', flightNo: null, isMine: false, isImportant: false, createdAt: at('14:00') },
  ],
  weather: { observedAt: at('14:00'), condition: 'CLEAR', temperature: 18, windSpeed: 4.2, windDirection: 315, visibility: 10, pressure: 1016,
    crosswind: { runway: '15/33', direction: 270, speed: 2.1 },
    operationScore: { minutesAhead: 60, score: null, level: null, basis: null, message: '운항 확률 예측은 검증 예정입니다.' } },
  facilities: [
    facility('f1', '마티나 라운지', 'LOUNGE', 'T1', '4F', '면세지역 43번 게이트 부근', '07:00', '22:00', true),
    facility('f2', '커피 & 베이커리', 'FOOD_CAFE', 'T2', '3F', '일반지역 중앙', '06:00', '22:00', true),
    facility('f3', '공항 약국', 'PHARMACY', 'T1', '3F', '일반지역 서편', '07:00', '21:00', true),
    facility('f4', '트래블 숍', 'SHOPPING', 'T2', '3F', '면세지역 250번 게이트 부근', '06:30', '21:30', true),
    facility('f5', '여행자 안내센터', 'ETC', 'T1', '1F', '일반지역 동편', '09:00', '14:00', false),
  ],
};

