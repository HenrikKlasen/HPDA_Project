import HorizontalBarChart from '../components/charts/HorizontalBarChart';
import MultiLineChart from '../components/charts/MultiLineChart';
import WorkforceFlowChart from '../components/charts/WorkforceFlowChart';
import KpiCard from '../components/kpi/KpiCard';
import { mockEmployment, mockWorkforceTransitions } from '../data/mockEconomics';

function ReportsPage() {
  const { employerSize, turnoverRates, hiringTrend } = mockEmployment;

  const totalEmployers = employerSize.length;
  const totalEmployees = employerSize.reduce((sum, e) => sum + e.value, 0);
  const overallTurnover = (turnoverRates.reduce((sum, e) => sum + e.value, 0) / turnoverRates.length).toFixed(1);

  return (
    <section>
      <h2 className="section-title">Job Market</h2>
      <p className="page-subtitle">Employer size, turnover rates, and monthly hiring patterns across the city.</p>

      <div className="grid kpis">
        <KpiCard title="Total Employers" value={totalEmployers} />
        <KpiCard title="Total Employees" value={totalEmployees} />
        <KpiCard title="Avg Tenure" value="14.2 mo" />
        <KpiCard title="Overall Turnover" value={`${overallTurnover}%`} />
      </div>

      <div className="grid charts">
        <HorizontalBarChart data={employerSize} title="Employees per Employer" />
        <HorizontalBarChart
          data={turnoverRates}
          title="Annual Turnover Rate by Employer"
          valueFormat={(v) => `${v}%`}
        />
        <MultiLineChart data={hiringTrend} title="Monthly Hires vs Departures" />
        <WorkforceFlowChart data={mockWorkforceTransitions} title="Sector-to-Sector Workforce Transitions" />
      </div>
    </section>
  );
}

export default ReportsPage;
