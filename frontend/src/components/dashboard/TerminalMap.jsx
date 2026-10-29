import { Plane, MapPin } from 'lucide-react';
import StatusBadge from '../common/StatusBadge.jsx';
export default function TerminalMap({ terminal, floor, halls, selectedHallId, onSelectHall }) {
  const selected = halls.find(hall => hall.hallId === selectedHallId);
  return <div className="terminal-map">
    <div className="map-caption"><span><MapPin size={14} />{terminal === 'T1' ? '제1여객터미널' : '제2여객터미널'}</span><span>{floor} · 개념도</span></div>
    <svg className="terminal-drawing" viewBox="0 0 620 370" role="img" aria-label={`${terminal} ${floor} 시연용 터미널 도식, 실제 공항 동선과 다릅니다`}>
      <defs><pattern id="grid" width="22" height="22" patternUnits="userSpaceOnUse"><path d="M 22 0 L 0 0 0 22" fill="none" stroke="#e2e9f1" strokeWidth="0.6" /></pattern></defs>
      <rect width="620" height="370" fill="url(#grid)" />
      <path d={terminal === 'T1' ? 'M50 80 L205 105 L240 136 L380 136 L415 105 L570 80 L570 139 L432 168 L390 199 L230 199 L188 168 L50 139 Z' : 'M60 76 L215 113 L250 148 L370 148 L405 113 L560 76 L580 130 L427 176 L390 212 L230 212 L193 176 L40 130 Z'} fill="#d6e2ee" stroke="#aabed2" strokeWidth="2" />
      <rect x="118" y="221" width="384" height="89" rx="15" fill="#fff" stroke="#b8cadc" strokeWidth="2" />
      <path d="M250 199 V220 M370 199 V220" stroke="#b8cadc" strokeWidth="18" />
      <path d="M143 254 H477 M143 276 H477" stroke="#e1e9f1" strokeWidth="7" strokeDasharray="35 10" />
      <text x="310" y="177" textAnchor="middle" fill="#667c94" fontSize="13">AIR SIDE · 탑승 구역</text>
      <text x="310" y="338" textAnchor="middle" fill="#8091a4" fontSize="12">{floor === '3F' ? '출발 · 체크인 구역' : floor === '2F' ? '연결 · 편의시설 구역' : '도착 · 입국 구역'}</text>
    </svg>
    <Plane className="map-plane" size={23} aria-hidden="true" />
    {floor === '3F' ? <div className="map-markers">{halls.map(hall => <button key={hall.hallId} className={`map-marker ${hall.level.toLowerCase()} ${selectedHallId === hall.hallId ? 'selected' : ''}`} aria-label={`${hall.hallName} ${hall.waitingCount}명`} aria-pressed={selectedHallId === hall.hallId} onClick={() => onSelectHall(hall.hallId)}>{hall.hallId}</button>)}</div> : <div className="floor-notice">{floor} 시설 배치는 준비 중입니다.<br />출국장 마커는 3F에서 확인하세요.</div>}
    <div className="map-selection">{floor === '3F' && selected ? <><strong>{selected.hallName}</strong><StatusBadge status={selected.level} /><span>대기 {selected.waitingCount}명</span></> : <span>{floor} 층 보기</span>}</div>
  </div>;
}

