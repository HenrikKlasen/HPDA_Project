import React, { useEffect, useState, useRef } from "react";
import { useParams, Link } from "react-router-dom";
import * as d3 from "d3";
import LoadingSpinner from "../components/common/LoadingSpinner";

function EmployerFinancialsDashboard() {
  const { id } = useParams();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const revenueChartRef = useRef(null);
  const profitChartRef = useRef(null);
  const employeeChartRef = useRef(null);

  useEffect(() => {
    fetch(`http://localhost:5000/api/employer_financials_timeline/${id}`)
      .then((res) => res.json())
      .then((d) => {
        setData(d);
        setLoading(false);
      })
      .catch((err) => {
        setError(err.message);
        setLoading(false);
      });
  }, [id]);

  useEffect(() => {
    if (!data || !data.monthly || !revenueChartRef.current) return;

    // Revenue Chart
    drawChart(
      revenueChartRef.current,
      data.monthly,
      "revenue",
      "Revenue Over Time",
      "#3b82f6",
    );
  }, [data]);

  useEffect(() => {
    if (!data || !data.monthly || !profitChartRef.current) return;

    // Profit Chart
    drawChart(
      profitChartRef.current,
      data.monthly,
      "profit",
      "Profit Over Time",
      "#10b981",
    );
  }, [data]);

  useEffect(() => {
    if (!data || !data.monthly || !employeeChartRef.current) return;

    // Employee Chart
    drawEmployeeChart(employeeChartRef.current, data.monthly);
  }, [data]);

  const drawChart = (container, dataset, key, title, color) => {
    if (!container || dataset.length === 0) return;

    d3.select(container).selectAll("*").remove();

    const margin = { top: 20, right: 30, bottom: 30, left: 60 };
    const width = container.clientWidth - margin.left - margin.right;
    const height = 300 - margin.top - margin.bottom;

    const svg = d3
      .select(container)
      .append("svg")
      .attr("width", width + margin.left + margin.right)
      .attr("height", height + margin.top + margin.bottom)
      .append("g")
      .attr("transform", `translate(${margin.left},${margin.top})`);

    const xScale = d3
      .scaleLinear()
      .domain([0, dataset.length - 1])
      .range([0, width]);

    const yScale = d3
      .scaleLinear()
      .domain([0, d3.max(dataset, (d) => d[key]) * 1.1])
      .range([height, 0]);

    // Line generator
    const line = d3
      .line()
      .x((d, i) => xScale(i))
      .y((d) => yScale(d[key]));

    // Draw grid
    svg
      .append("g")
      .attr("class", "grid")
      .attr("opacity", 0.1)
      .call(d3.axisLeft(yScale).tickSize(-width).tickFormat(""));

    // Draw path
    svg
      .append("path")
      .datum(dataset)
      .attr("fill", "none")
      .attr("stroke", color)
      .attr("stroke-width", 2.5)
      .attr("d", line);

    // Draw dots
    svg
      .selectAll(".dot")
      .data(dataset)
      .enter()
      .append("circle")
      .attr("class", "dot")
      .attr("cx", (d, i) => xScale(i))
      .attr("cy", (d) => yScale(d[key]))
      .attr("r", 4)
      .attr("fill", color)
      .attr("opacity", 0.7)
      .on("mouseover", function (event, d) {
        d3.select(this).attr("r", 6).attr("opacity", 1);
      })
      .on("mouseout", function () {
        d3.select(this).attr("r", 4).attr("opacity", 0.7);
      });

    // X axis
    svg
      .append("g")
      .attr("transform", `translate(0,${height})`)
      .call(
        d3
          .axisBottom(xScale)
          .tickFormat((i) => dataset[i]?.month || dataset[i]?.week || ""),
      );

    // Y axis
    svg.append("g").call(d3.axisLeft(yScale));

    // Title
    svg
      .append("text")
      .attr("x", width / 2)
      .attr("y", -5)
      .attr("text-anchor", "middle")
      .attr("font-size", "14px")
      .attr("font-weight", "bold")
      .text(title);
  };

  const drawEmployeeChart = (container, dataset) => {
    if (!container || dataset.length === 0) return;

    d3.select(container).selectAll("*").remove();

    const margin = { top: 20, right: 30, bottom: 30, left: 60 };
    const width = container.clientWidth - margin.left - margin.right;
    const height = 300 - margin.top - margin.bottom;

    const svg = d3
      .select(container)
      .append("svg")
      .attr("width", width + margin.left + margin.right)
      .attr("height", height + margin.top + margin.bottom)
      .append("g")
      .attr("transform", `translate(${margin.left},${margin.top})`);

    const xScale = d3
      .scaleLinear()
      .domain([0, dataset.length - 1])
      .range([0, width]);

    const yScale = d3
      .scaleLinear()
      .domain([0, d3.max(dataset, (d) => d.max_employees) * 1.2])
      .range([height, 0]);

    // Draw bars for max employees
    svg
      .selectAll(".bar-max")
      .data(dataset)
      .enter()
      .append("rect")
      .attr("class", "bar-max")
      .attr("x", (d, i) => xScale(i) - 8)
      .attr("y", (d) => yScale(d.max_employees))
      .attr("width", 16)
      .attr("height", (d) => height - yScale(d.max_employees))
      .attr("fill", "#fbbf24")
      .attr("opacity", 0.6);

    // Draw line for avg employees
    const line = d3
      .line()
      .x((d, i) => xScale(i))
      .y((d) => yScale(d.avg_employees));

    svg
      .append("path")
      .datum(dataset)
      .attr("fill", "none")
      .attr("stroke", "#8b5cf6")
      .attr("stroke-width", 2.5)
      .attr("d", line);

    svg
      .selectAll(".dot")
      .data(dataset)
      .enter()
      .append("circle")
      .attr("cx", (d, i) => xScale(i))
      .attr("cy", (d) => yScale(d.avg_employees))
      .attr("r", 4)
      .attr("fill", "#8b5cf6")
      .attr("opacity", 0.7);

    // X axis
    svg
      .append("g")
      .attr("transform", `translate(0,${height})`)
      .call(d3.axisBottom(xScale).tickFormat((i) => dataset[i]?.month || ""));

    // Y axis
    svg.append("g").call(d3.axisLeft(yScale));

    // Title
    svg
      .append("text")
      .attr("x", width / 2)
      .attr("y", -5)
      .attr("text-anchor", "middle")
      .attr("font-size", "14px")
      .attr("font-weight", "bold")
      .text("Employee Count Over Time");

    // Legend
    const legend = svg.append("g").attr("font-size", "12px");

    legend
      .append("rect")
      .attr("x", width - 180)
      .attr("y", -40)
      .attr("width", 10)
      .attr("height", 10)
      .attr("fill", "#fbbf24");

    legend
      .append("text")
      .attr("x", width - 165)
      .attr("y", -32)
      .text("Max Employees");

    legend
      .append("line")
      .attr("x1", width - 180)
      .attr("y1", -25)
      .attr("x2", width - 170)
      .attr("y2", -25)
      .attr("stroke", "#8b5cf6")
      .attr("stroke-width", 2);

    legend
      .append("text")
      .attr("x", width - 165)
      .attr("y", -22)
      .text("Avg Employees");
  };

  if (loading)
    return (
      <div style={{ padding: "40px", textAlign: "center" }}>
        <LoadingSpinner message="Loading financial data..." />
        <div style={{ fontSize: "12px", color: "#999", marginTop: "8px" }}>
          This may take a moment while aggregating all participant logs
        </div>
      </div>
    );
  if (error)
    return (
      <div
        style={{
          padding: "20px",
          background: "#fee2e2",
          color: "#991b1b",
          borderRadius: "8px",
          margin: "20px",
        }}
      >
        ⚠️ Error: {error}
      </div>
    );
  if (!data)
    return (
      <div style={{ padding: "20px", textAlign: "center", color: "#999" }}>
        No data found for this employer
      </div>
    );

  const fmtCurrency = (v) =>
    new Intl.NumberFormat(undefined, {
      style: "currency",
      currency: "USD",
      maximumFractionDigits: 0,
    }).format(v);

  return (
    <section style={{ padding: "20px", background: "#f9fafb" }}>
      <div
        style={{
          display: "flex",
          gap: 12,
          alignItems: "center",
          marginBottom: 20,
        }}
      >
        <h2>{data.employer_name} Details</h2>
        <Link
          to="/business"
          state={{ viewMode: 'map', selectedEmployerId: id }}
          style={{
            marginLeft: "auto",
            fontSize: "14px",
            background: "#2f5d8c",
            color: "white",
            padding: "8px 16px",
            borderRadius: "6px",
            textDecoration: "none",
            fontWeight: "bold",
            display: "inline-block",
            boxShadow: "0 2px 4px rgba(0,0,0,0.1)",
            transition: "all 0.2s ease"
          }}
          onMouseOver={(e) => e.currentTarget.style.background = "#1e4066"}
          onMouseOut={(e) => e.currentTarget.style.background = "#2f5d8c"}
        >
          ← Back to Map Explorer
        </Link>
      </div>

      {/* Summary Cards */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))",
          gap: 12,
          marginBottom: 20,
        }}
      >
        <div
          style={{
            background: "#fff",
            padding: 16,
            borderRadius: 8,
            boxShadow: "0 1px 3px rgba(0,0,0,.1)",
          }}
        >
          <div style={{ fontSize: "12px", color: "#666" }}>
            Avg Daily Revenue
          </div>
          <div style={{ fontSize: "20px", fontWeight: "bold", marginTop: 4 }}>
            {fmtCurrency(data.summary.avg_daily_revenue)}
          </div>
        </div>
        <div
          style={{
            background: "#fff",
            padding: 16,
            borderRadius: 8,
            boxShadow: "0 1px 3px rgba(0,0,0,.1)",
          }}
        >
          <div style={{ fontSize: "12px", color: "#666" }}>
            Avg Daily Profit
          </div>
          <div
            style={{
              fontSize: "20px",
              fontWeight: "bold",
              marginTop: 4,
              color: "#10b981",
            }}
          >
            {fmtCurrency(data.summary.avg_daily_profit)}
          </div>
        </div>
        <div
          style={{
            background: "#fff",
            padding: 16,
            borderRadius: 8,
            boxShadow: "0 1px 3px rgba(0,0,0,.1)",
          }}
        >
          <div style={{ fontSize: "12px", color: "#666" }}>Total Revenue</div>
          <div style={{ fontSize: "20px", fontWeight: "bold", marginTop: 4 }}>
            {fmtCurrency(data.summary.total_revenue)}
          </div>
        </div>
        <div
          style={{
            background: "#fff",
            padding: 16,
            borderRadius: 8,
            boxShadow: "0 1px 3px rgba(0,0,0,.1)",
          }}
        >
          <div style={{ fontSize: "12px", color: "#666" }}>Total Profit</div>
          <div
            style={{
              fontSize: "20px",
              fontWeight: "bold",
              marginTop: 4,
              color: "#10b981",
            }}
          >
            {fmtCurrency(data.summary.total_profit)}
          </div>
        </div>
        <div
          style={{
            background: "#fff",
            padding: 16,
            borderRadius: 8,
            boxShadow: "0 1px 3px rgba(0,0,0,.1)",
          }}
        >
          <div style={{ fontSize: "12px", color: "#666" }}>Avg Employees</div>
          <div style={{ fontSize: "20px", fontWeight: "bold", marginTop: 4 }}>
            {data.summary.avg_employees.toFixed(1)}
          </div>
        </div>
        <div
          style={{
            background: "#fff",
            padding: 16,
            borderRadius: 8,
            boxShadow: "0 1px 3px rgba(0,0,0,.1)",
          }}
        >
          <div style={{ fontSize: "12px", color: "#666" }}>Hourly Rate</div>
          <div style={{ fontSize: "20px", fontWeight: "bold", marginTop: 4 }}>
            ${data.avg_hourly_rate.toFixed(2)}
          </div>
        </div>
      </div>

      {/* Charts */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "1fr 1fr",
          gap: 20,
          marginBottom: 20,
        }}
      >
        <div
          style={{
            background: "#fff",
            padding: 16,
            borderRadius: 8,
            boxShadow: "0 1px 3px rgba(0,0,0,.1)",
          }}
        >
          <div
            ref={revenueChartRef}
            style={{ width: "100%", height: "350px" }}
          ></div>
        </div>
        <div
          style={{
            background: "#fff",
            padding: 16,
            borderRadius: 8,
            boxShadow: "0 1px 3px rgba(0,0,0,.1)",
          }}
        >
          <div
            ref={profitChartRef}
            style={{ width: "100%", height: "350px" }}
          ></div>
        </div>
      </div>

      <div
        style={{
          background: "#fff",
          padding: 16,
          borderRadius: 8,
          boxShadow: "0 1px 3px rgba(0,0,0,.1)",
          marginBottom: 20,
        }}
      >
        <div
          ref={employeeChartRef}
          style={{ width: "100%", height: "350px" }}
        ></div>
      </div>

      {/* Monthly Table */}
      <div
        style={{
          background: "#fff",
          padding: 16,
          borderRadius: 8,
          boxShadow: "0 1px 3px rgba(0,0,0,.1)",
        }}
      >
        <h3 style={{ marginTop: 0 }}>Monthly Breakdown</h3>
        <table
          style={{
            width: "100%",
            borderCollapse: "collapse",
            fontSize: "13px",
          }}
        >
          <thead>
            <tr style={{ borderBottom: "1px solid #e5e7eb" }}>
              <th style={{ textAlign: "left", padding: 8 }}>Month</th>
              <th style={{ textAlign: "right", padding: 8 }}>Avg Employees</th>
              <th style={{ textAlign: "right", padding: 8 }}>Revenue</th>
              <th style={{ textAlign: "right", padding: 8 }}>Payroll</th>
              <th style={{ textAlign: "right", padding: 8 }}>Operating</th>
              <th style={{ textAlign: "right", padding: 8 }}>Profit</th>
            </tr>
          </thead>
          <tbody>
            {data.monthly.map((m, i) => (
              <tr
                key={i}
                style={{
                  borderBottom: "1px solid #f3f4f6",
                  backgroundColor: i % 2 === 0 ? "#fafafa" : "#fff",
                }}
              >
                <td style={{ padding: 8 }}>{m.month}</td>
                <td style={{ textAlign: "right", padding: 8 }}>
                  {m.avg_employees.toFixed(1)}
                </td>
                <td style={{ textAlign: "right", padding: 8 }}>
                  {fmtCurrency(m.revenue)}
                </td>
                <td style={{ textAlign: "right", padding: 8 }}>
                  {fmtCurrency(m.payroll)}
                </td>
                <td style={{ textAlign: "right", padding: 8 }}>
                  {fmtCurrency(m.operating)}
                </td>
                <td
                  style={{
                    textAlign: "right",
                    padding: 8,
                    fontWeight: "bold",
                    color: "#10b981",
                  }}
                >
                  {fmtCurrency(m.profit)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

export default EmployerFinancialsDashboard;
