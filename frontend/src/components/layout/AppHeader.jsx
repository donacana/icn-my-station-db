import { useState } from 'react';
import { Plane, Search, Home, Map, RadioTower, ChartNoAxesCombined, CloudSun, Coffee, Bell } from 'lucide-react';
import { useClock } from '../../hooks/useClock.js';
import { date, time } from '../../utils/formatters.js';

export const menus = [
  ['home', '홈', Home], ['congestion', '출국장 혼잡도', Map], ['flights', '운항 현황', RadioTower],
  ['statistics', '운항 통계', ChartNoAxesCombined], ['weather', '날씨·운항 확률', CloudSun],
  ['facilities', '편의시설', Coffee], ['alerts', '스마트 알림', Bell],
];
export default function AppHeader({ page, onNavigate, flights, selectedFlight, onSelectFlight }) {
  const now = useClock();
  const [query, setQuery] = useState('');
  const [message, setMessage] = useState('');
  function search(event) {
    event.preventDefault();
    const normalized = query.replace(/\s/g, '').toUpperCase();
    const match = flights.find(flight => flight.flightNo === normalized);
    if (!match) { setMessage('일치하는 시연 항공편이 없습니다. KE703, OZ102, KE671을 검색해 보세요.'); return; }
    onSelectFlight(match);
    onNavigate('home');
    setMessage(`${match.flightNo} 항공편을 선택했습니다.`);
  }
  return <header className="app-header">
    <div className="header-main">
      <button className="brand" onClick={() => onNavigate('home')} aria-label="ICN My Station 홈"><span className="brand-icon"><Plane size={25} /></span><span><strong>ICN <span>My Station</span></strong><small>인천공항, 나의 여정을 한눈에</small></span></button>
      <div className="search-wrap"><form onSubmit={search} className="flight-search"><Search size={18} /><input aria-label="항공편 번호" placeholder="내 항공편 찾기  ·  예: KE703" value={query} onChange={e => setQuery(e.target.value)} /><button type="submit">검색</button></form><p className="search-message" role="status">{message}</p></div>
      <div className="header-clock"><span>{date(now)}</span><strong>{time(now)}<small>KST</small></strong></div>
      <span className="demo-tag">DEMO · 시연용</span>
    </div>
    <nav className="main-nav" aria-label="주 메뉴">{menus.map(([id, label, Icon]) => <button key={id} onClick={() => onNavigate(id)} className={page === id ? 'active' : ''} aria-current={page === id ? 'page' : undefined}><Icon size={16} />{label}</button>)}
    <span className="nav-flight">{selectedFlight ? `나의 항공편 · ${selectedFlight.flightNo}` : '나의 여정을 시작해 보세요'}</span></nav>
  </header>;
}

