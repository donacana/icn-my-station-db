import { useState } from 'react';
import { Map, Info } from 'lucide-react';
import Panel from '../common/Panel.jsx';
import TerminalMap from './TerminalMap.jsx';
import ExitCongestionCards from './ExitCongestionCards.jsx';
import { time } from '../../utils/formatters.js';
export default function CongestionSection({ congestion }) {
  const [terminal, setTerminal] = useState('T1');
  const [floor, setFloor] = useState('3F');
  const [selectedByTerminal, setSelectedByTerminal] = useState({});
  const current = congestion[terminal];
  const selectedHallId = selectedByTerminal[terminal] ?? current.halls[0]?.hallId;
  const select = hallId => setSelectedByTerminal(prev => ({ ...prev, [terminal]: hallId }));
  return <Panel title="출국장 혼잡도" eyebrow="TERMINAL GUIDE" icon={Map} className="congestion-panel" action={<span className="quiet-label">{time(current.measuredAt)} 기준</span>}>
    <div className="map-toolbar"><div className="segmented terminal-tabs">{Object.keys(congestion).map(id => <button key={id} onClick={() => setTerminal(id)} aria-pressed={terminal === id}>{id} <span>{id === 'T1' ? '제1터미널' : '제2터미널'}</span></button>)}</div><div className="legend"><span><i className="green" />원활</span><span><i className="orange" />보통</span><span><i className="red" />혼잡</span></div></div>
    <div className="map-frame"><TerminalMap terminal={terminal} floor={floor} halls={current.halls} selectedHallId={selectedHallId} onSelectHall={select} /><div className="floor-tabs" aria-label="층 선택">{['3F', '2F', '1F'].map(item => <button key={item} aria-pressed={floor === item} onClick={() => setFloor(item)}>{item}</button>)}</div></div>
    <div className="section-subtitle"><h3>출국장별 대기 현황</h3><span>단위: 명</span></div>
    <ExitCongestionCards halls={current.halls} selectedHallId={selectedHallId} onSelectHall={id => { select(id); setFloor('3F'); }} />
    <div className="map-info"><Info size={16} /><p>지도와 대기인원은 시연용입니다. 실제 위치·이동 경로를 안내하지 않습니다.<br />변화율은 API 계약에 따라 전일 같은 시각 대비 예시로 표시합니다.</p></div>
  </Panel>;
}

