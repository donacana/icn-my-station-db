import { PlaneTakeoff, ArrowUpRight } from 'lucide-react';
import Panel from '../common/Panel.jsx';
import StatusBadge from '../common/StatusBadge.jsx';
import { time } from '../../utils/formatters.js';
export default function FlightBoard({ flights, direction, onDirectionChange, selectedFlight, onSelectFlight, onDetail }) {
  const rows = direction === 'departure' ? flights.departures : flights.arrivals;
  return <Panel title="운항 현황" icon={PlaneTakeoff} action={<button className="icon-button" aria-label="운항 현황 상세" onClick={onDetail}><ArrowUpRight size={18} /></button>}>
    <div className="segmented"><button aria-pressed={direction === 'departure'} onClick={() => onDirectionChange('departure')}>출발</button><button aria-pressed={direction === 'arrival'} onClick={() => onDirectionChange('arrival')}>도착</button></div>
    <div className="board-labels"><span>시간 / 항공편</span><span>{direction === 'departure' ? '목적지' : '출발지'}</span><span>상태</span></div>
    <div className="flight-rows">{rows.map(flight => <button className={`flight-row ${selectedFlight?.uniqCode === flight.uniqCode ? 'selected' : ''}`} aria-pressed={selectedFlight?.uniqCode === flight.uniqCode} key={flight.uniqCode} onClick={() => onSelectFlight(flight)}>
      <span><strong className={flight.estimatedAt ? 'old-time' : ''}>{time(flight.scheduledAt)}</strong>{flight.estimatedAt && <strong className="new-time">{time(flight.estimatedAt)}</strong>}<small>{flight.flightNo}</small></span>
      <span><b>{flight.city}</b><small>{flight.terminal} · GATE {flight.gate ?? '미정'}</small></span><StatusBadge status={flight.status} />
    </button>)}</div><p className="panel-footnote">항공편을 선택하면 나의 알림에 연결됩니다.</p>
  </Panel>;
}

