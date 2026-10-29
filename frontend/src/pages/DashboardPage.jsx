import { useState } from 'react';
import { RefreshCw, ArrowRight, Plane, X } from 'lucide-react';
import FlightBoard from '../components/dashboard/FlightBoard.jsx';
import FlightStatistics from '../components/dashboard/FlightStatistics.jsx';
import CongestionSection from '../components/dashboard/CongestionSection.jsx';
import AlertList from '../components/dashboard/AlertList.jsx';
import WeatherCard from '../components/dashboard/WeatherCard.jsx';
import FacilityPreview from '../components/dashboard/FacilityPreview.jsx';
import StatusBadge from '../components/common/StatusBadge.jsx';
import { date, time } from '../utils/formatters.js';
export default function DashboardPage({ data, loading, error, refresh, selectedFlight, onSelectFlight, onNavigate }) {
  const [direction, setDirection] = useState('departure');
  if (!data) return <main className="loading-state" role="status">{error || '대시보드를 불러오는 중입니다…'}{error && <button className="primary-button" onClick={refresh}>다시 시도</button>}</main>;
  return <main className="dashboard">
    <div className="page-heading"><div><span className="eyebrow">INCHEON AIRPORT DASHBOARD</span><h1>공항의 모든 순간, 한눈에</h1><p>출국장부터 탑승구까지, 오늘의 공항 정보를 확인하세요.</p></div><button className="refresh-button" onClick={refresh} disabled={loading}><RefreshCw size={15} />시연 데이터 다시 불러오기</button></div>
    <div className="demo-banner"><span><strong>시연용 데이터</strong> 실제 실시간 정보가 아닙니다.</span><span>고정 기준: {date(data.generatedAt)} {time(data.generatedAt)} KST</span></div>
    {error && <div className="error-banner" role="alert">{error}<button onClick={refresh}>다시 시도</button></div>}
    {selectedFlight && <div className="my-flight"><Plane size={20} /><strong>나의 항공편 · {selectedFlight.flightNo}</strong><span>인천 {selectedFlight.type === 'DEPARTURE' ? <ArrowRight size={14} /> : '←'} {selectedFlight.city}</span><span>{selectedFlight.terminal} · {selectedFlight.gate ?? '미정'}번 게이트</span><StatusBadge status={selectedFlight.status} /><button className="icon-button" aria-label="항공편 선택 해제" onClick={() => onSelectFlight(null)}><X size={17} /></button></div>}
    <div className="dashboard-grid">
      <div className="dashboard-column left-column"><FlightBoard flights={data.flights} direction={direction} onDirectionChange={setDirection} selectedFlight={selectedFlight} onSelectFlight={onSelectFlight} onDetail={() => onNavigate('flights')} /><FlightStatistics stats={data.stats[direction]} /></div>
      <div className="dashboard-column center-column"><CongestionSection congestion={data.congestion} /><div className="journey-note"><span className="journey-icon"><Plane size={25} /></span><div><h3>여유로운 출발의 시작</h3><p>나의 항공편을 선택하고 탑승구와 알림을 함께 확인하세요.</p></div><ArrowRight size={20} /></div></div>
      <div className="dashboard-column right-column"><AlertList alerts={data.alerts} selectedFlight={selectedFlight} /><WeatherCard weather={data.weather} /><FacilityPreview facilities={data.facilities} /></div>
    </div>
    <footer className="app-footer"><strong>ICN My Station</strong><span>인천공항 통합 대시보드 · Mock Prototype</span><span>모든 정보는 시연용이며 실제 여행에 사용하지 마세요.</span></footer>
  </main>;
}

