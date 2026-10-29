import { TrendingDown, TrendingUp } from 'lucide-react';
import StatusBadge from '../common/StatusBadge.jsx';
export default function ExitCongestionCards({ halls, selectedHallId, onSelectHall }) {
  return <div className="hall-cards">{halls.map(hall => <button key={hall.hallId} className={`hall-card ${selectedHallId === hall.hallId ? 'selected' : ''}`} aria-pressed={selectedHallId === hall.hallId} onClick={() => onSelectHall(hall.hallId)}><span className="hall-name">{hall.hallName}<StatusBadge status={hall.level} /></span><strong>{hall.waitingCount}<small>명 대기</small></strong><span className={`change ${hall.changeRate > 0 ? 'increase' : ''}`}>{hall.changeRate > 0 ? <TrendingUp size={13} /> : <TrendingDown size={13} />}{hall.changeRate === null ? '비교값 없음' : `${hall.changeRate > 0 ? '+' : ''}${hall.changeRate}%`}<small>전일 대비</small></span></button>)}</div>;
}

