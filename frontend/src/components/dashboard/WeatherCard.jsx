import { CloudSun, Sun, Navigation, Wind } from 'lucide-react';
import Panel from '../common/Panel.jsx';
import { time, windLabel } from '../../utils/formatters.js';
export default function WeatherCard({ weather }) {
  return <Panel title="공항 날씨" icon={CloudSun} action={<span className="quiet-label">{time(weather.observedAt)} 관측</span>}>
    <div className="weather-main"><Sun size={48} strokeWidth={1.3} /><div><strong>{weather.temperature}<small>°C</small></strong><span>{{ CLEAR: '맑음', CLOUDY: '흐림', RAIN: '비', SNOW: '눈', FOG: '안개' }[weather.condition] ?? '정보 없음'}</span></div><div className="compass" aria-label={`풍향 ${windLabel(weather.windDirection)} ${weather.windDirection}도`}><span>N</span><Navigation style={{ transform: `rotate(${weather.windDirection - 45}deg)` }} size={25} /><small>{windLabel(weather.windDirection)}풍</small></div></div>
    <dl className="weather-details"><div><dt><Wind size={13} />풍속</dt><dd>{weather.windSpeed} <small>m/s</small></dd></div><div><dt>시정</dt><dd>{weather.visibility} <small>km</small></dd></div><div><dt>기압</dt><dd>{weather.pressure} <small>hPa</small></dd></div></dl>
    <div className="prediction-note"><span>운항 확률</span><b>검증 예정</b><p>현재 예측 결과를 제공하지 않습니다.</p></div>
  </Panel>;
}

