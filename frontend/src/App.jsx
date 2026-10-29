import { useState } from 'react';
import AppHeader, { menus } from './components/layout/AppHeader.jsx';
import DashboardPage from './pages/DashboardPage.jsx';
import DetailPage from './pages/DetailPage.jsx';
import { useDashboard } from './hooks/useDashboard.js';

export default function App() {
  const dashboard = useDashboard();
  const [page, setPage] = useState('home');
  const [selectedFlight, setSelectedFlight] = useState(null);
  const flights = dashboard.data ? [...dashboard.data.flights.departures, ...dashboard.data.flights.arrivals] : [];
  return <><AppHeader page={page} onNavigate={setPage} flights={flights} selectedFlight={selectedFlight} onSelectFlight={setSelectedFlight} />
    {page === 'home' ? <DashboardPage {...dashboard} selectedFlight={selectedFlight} onSelectFlight={setSelectedFlight} onNavigate={setPage} /> : <DetailPage title={menus.find(([id]) => id === page)?.[1]} onHome={() => setPage('home')} />}
  </>;
}

