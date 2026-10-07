import React, { useMemo, useRef } from 'react';
import { HourlyForecastRecord } from '../types';
import { ChevronLeftIcon, ChevronRightIcon, ClockIcon } from './Icons';

interface ForecastChartProps {
  forecast: HourlyForecastRecord[];
  selectedHourIndex: number;
  onSelectHour: (index: number) => void;
  units: string;
  onPrevHour: () => void;
  onNextHour: () => void;
  isLoading: boolean;
}

export const ForecastChart: React.FC<ForecastChartProps> = ({
  forecast,
  selectedHourIndex,
  onSelectHour,
  units,
  onPrevHour,
  onNextHour,
  isLoading,
}) => {
  const svgRef = useRef<SVGSVGElement | null>(null);

  const chartMetrics = useMemo(() => {
    const width = 860;
    const height = 240;
    const padLeft = 55;
    const padRight = 20;
    const padTop = 20;
    const padBottom = 40;
    const plotWidth = width - padLeft - padRight;
    const plotHeight = height - padTop - padBottom;

    if (!forecast || forecast.length === 0) {
      return {
        minVal: 0,
        maxVal: 300,
        points: '',
        fillPath: '',
        width,
        height,
        padLeft,
        padRight,
        padTop,
        padBottom,
        plotWidth,
        plotHeight,
        coords: [],
      };
    }

    const values = forecast.map((f) => f.pm25);
    const minRaw = Math.min(...values);
    const maxRaw = Math.max(...values);
    const padding = 15;
    const minVal = Math.max(0, Math.floor(minRaw - padding));
    const maxVal = Math.ceil(maxRaw + padding);
    const range = maxVal - minVal || 1;

    const coords = forecast.map((rec, i) => {
      const x = padLeft + (i / (forecast.length - 1)) * plotWidth;
      const y = padTop + plotHeight - ((rec.pm25 - minVal) / range) * plotHeight;
      return { x, y, record: rec };
    });

    const pointsStr = coords.map((c) => `${c.x.toFixed(1)},${c.y.toFixed(1)}`).join(' ');
    const firstX = coords[0].x.toFixed(1);
    const lastX = coords[coords.length - 1].x.toFixed(1);
    const bottomY = (padTop + plotHeight).toFixed(1);
    const fillPath = `M ${firstX},${bottomY} L ${pointsStr.replace(/ /g, ' L ')} L ${lastX},${bottomY} Z`;

    return {
      minVal,
      maxVal,
      width,
      height,
      padLeft,
      padRight,
      padTop,
      padBottom,
      plotWidth,
      plotHeight,
      coords,
      points: pointsStr,
      fillPath,
    };
  }, [forecast]);

  const handlePointerInteraction = (e: React.PointerEvent<SVGSVGElement>) => {
    if (!svgRef.current || !forecast.length) return;
    const rect = svgRef.current.getBoundingClientRect();
    const clientX = e.clientX - rect.left;
    const ratio =
      (clientX - (chartMetrics.padLeft / chartMetrics.width) * rect.width) /
      ((chartMetrics.plotWidth / chartMetrics.width) * rect.width);
    const boundedRatio = Math.max(0, Math.min(1, ratio));
    const targetIdx = Math.round(boundedRatio * (forecast.length - 1));
    if (targetIdx >= 0 && targetIdx < forecast.length) {
      onSelectHour(targetIdx);
    }
  };

  const selectedCoord = chartMetrics.coords?.[selectedHourIndex];
  const selectedRecord = forecast[selectedHourIndex];

  // Formatting selected timestamp in IST
  let istSelected = '';
  if (selectedRecord?.timestamp_utc) {
    try {
      const d = new Date(selectedRecord.timestamp_utc);
      istSelected = new Intl.DateTimeFormat('en-IN', {
        timeZone: 'Asia/Kolkata',
        day: 'numeric',
        month: 'short',
        hour: '2-digit',
        minute: '2-digit',
        hour12: true,
      }).format(d) + ' IST';
    } catch {
      istSelected = '';
    }
  }

  return (
    <section className="chart-card" aria-label="72-Hour PM2.5 Forecast Trajectory and Time Slider">
      <div className="chart-header">
        <div className="chart-title-group">
          <h2 className="chart-title">72-Hour PM2.5 Forecast Timeline</h2>
          <span className="chart-sub">
            Click or drag across the chart to scrub through the 72-hour horizon (T+0h to T+71h)
          </span>
        </div>
        <div className="chart-legend-badge">
          <span className="legend-indicator"></span>
          <span>PM2.5 ({units}) — Not AQI</span>
        </div>
      </div>

      <div className="svg-container">
        {isLoading && (
          <div className="chart-loading-overlay">
            <span>Updating timeline...</span>
          </div>
        )}

        <svg
          ref={svgRef}
          viewBox={`0 0 ${chartMetrics.width} ${chartMetrics.height}`}
          className="forecast-svg"
          onPointerDown={handlePointerInteraction}
          onPointerMove={(e) => {
            if (e.buttons === 1) handlePointerInteraction(e);
          }}
          aria-label="72-Hour PM2.5 Interactive Time-Series Chart"
        >
          <defs>
            <linearGradient id="pm25Gradient" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#14b8a6" stopOpacity="0.4" />
              <stop offset="100%" stopColor="#0a0f1d" stopOpacity="0.02" />
            </linearGradient>
            <linearGradient id="lineGlow" x1="0" y1="0" x2="1" y2="0">
              <stop offset="0%" stopColor="#2dd4bf" />
              <stop offset="50%" stopColor="#0ea5e9" />
              <stop offset="100%" stopColor="#38bdf8" />
            </linearGradient>
          </defs>

          {/* Horizontal grid lines & Y labels */}
          {[0, 0.25, 0.5, 0.75, 1].map((pct) => {
            const y = chartMetrics.padTop + chartMetrics.plotHeight * (1 - pct);
            const val = Math.round(
              chartMetrics.minVal + pct * (chartMetrics.maxVal - chartMetrics.minVal),
            );
            return (
              <g key={pct}>
                <line
                  x1={chartMetrics.padLeft}
                  y1={y}
                  x2={chartMetrics.width - chartMetrics.padRight}
                  y2={y}
                  stroke="rgba(148, 163, 184, 0.15)"
                  strokeDasharray="4 4"
                />
                <text
                  x={chartMetrics.padLeft - 10}
                  y={y + 4}
                  textAnchor="end"
                  fill="#94a3b8"
                  fontSize="11"
                  fontFamily="Inter, sans-serif"
                >
                  {val}
                </text>
              </g>
            );
          })}

          {/* Vertical boundary lines at T+24h and T+48h */}
          {[24, 48].map((hour) => {
            const x = chartMetrics.padLeft + (hour / 71) * chartMetrics.plotWidth;
            return (
              <g key={hour}>
                <line
                  x1={x}
                  y1={chartMetrics.padTop}
                  x2={x}
                  y2={chartMetrics.padTop + chartMetrics.plotHeight}
                  stroke="rgba(20, 184, 166, 0.25)"
                  strokeWidth="1.5"
                  strokeDasharray="5 5"
                />
                <text
                  x={x + 4}
                  y={chartMetrics.padTop + 14}
                  fill="#2dd4bf"
                  fontSize="10"
                  fontWeight="600"
                  fontFamily="Inter, sans-serif"
                >
                  +T{hour}h
                </text>
              </g>
            );
          })}

          {/* Time axis tick markers strictly labeled from T+0h to T+71h */}
          {[0, 12, 24, 36, 48, 60, 71].map((h) => {
            const x = chartMetrics.padLeft + (h / 71) * chartMetrics.plotWidth;
            return (
              <g key={`x-${h}`}>
                <line
                  x1={x}
                  y1={chartMetrics.padTop + chartMetrics.plotHeight}
                  x2={x}
                  y2={chartMetrics.padTop + chartMetrics.plotHeight + 5}
                  stroke="#64748b"
                />
                <text
                  x={x}
                  y={chartMetrics.padTop + chartMetrics.plotHeight + 20}
                  textAnchor="middle"
                  fill="#cbd5e1"
                  fontSize="11"
                  fontFamily="JetBrains Mono, monospace"
                >
                  T+{h}h
                </text>
              </g>
            );
          })}

          {/* Area fill */}
          {chartMetrics.fillPath && (
            <path d={chartMetrics.fillPath} fill="url(#pm25Gradient)" />
          )}

          {/* PM2.5 trajectory line */}
          {chartMetrics.points && (
            <polyline
              fill="none"
              stroke="url(#lineGlow)"
              strokeWidth="2.8"
              strokeLinecap="round"
              strokeLinejoin="round"
              points={chartMetrics.points}
            />
          )}

          {/* Selected hour indicator */}
          {selectedCoord && (
            <g>
              <line
                x1={selectedCoord.x}
                y1={chartMetrics.padTop}
                x2={selectedCoord.x}
                y2={chartMetrics.padTop + chartMetrics.plotHeight}
                stroke="#14b8a6"
                strokeWidth="2"
              />
              <circle
                cx={selectedCoord.x}
                cy={selectedCoord.y}
                r="6"
                fill="#14b8a6"
                stroke="#0a0f1d"
                strokeWidth="2.5"
              />
              <rect
                x={Math.max(
                  chartMetrics.padLeft + 5,
                  Math.min(selectedCoord.x - 45, chartMetrics.width - chartMetrics.padRight - 90),
                )}
                y={Math.max(chartMetrics.padTop + 4, selectedCoord.y - 32)}
                width="90"
                height="24"
                rx="4"
                fill="#0f172a"
                stroke="#14b8a6"
                strokeWidth="1"
              />
              <text
                x={Math.max(
                  chartMetrics.padLeft + 50,
                  Math.min(selectedCoord.x, chartMetrics.width - chartMetrics.padRight - 45),
                )}
                y={Math.max(chartMetrics.padTop + 20, selectedCoord.y - 16)}
                textAnchor="middle"
                fill="#f8fafc"
                fontSize="11"
                fontWeight="700"
                fontFamily="JetBrains Mono, monospace"
              >
                {selectedCoord.record.pm25} {units}
              </text>
            </g>
          )}
        </svg>
      </div>

      {/* Synchronized Shared Time Slider with Prev/Next buttons */}
      <div className="slider-control-bar">
        <div className="slider-header-row">
          <div className="slider-status-text">
            <ClockIcon size={16} className="slider-clock-icon" />
            <span>Forecast Lead Step:</span>
            <strong className="slider-lead-highlight">Hour {selectedHourIndex} (T+{selectedHourIndex}h)</strong>
            {istSelected && <span className="slider-time-ist">· {istSelected}</span>}
          </div>

          <div className="slider-nav-btns">
            <button
              type="button"
              className="slider-nav-btn"
              onClick={onPrevHour}
              disabled={selectedHourIndex <= 0}
              aria-label="Step back 1 hour"
              title="Previous hour"
            >
              <ChevronLeftIcon size={16} />
              <span>Prev</span>
            </button>
            <button
              type="button"
              className="slider-nav-btn"
              onClick={onNextHour}
              disabled={selectedHourIndex >= 71}
              aria-label="Step forward 1 hour"
              title="Next hour"
            >
              <span>Next</span>
              <ChevronRightIcon size={16} />
            </button>
          </div>
        </div>

        <input
          id="forecast-hour-slider"
          type="range"
          min="0"
          max="71"
          step="1"
          value={selectedHourIndex}
          onChange={(e) => onSelectHour(Number(e.target.value))}
          className="shared-time-slider"
          aria-label="72-Hour Forecast Time Slider"
        />

        <div className="slider-endpoints-row">
          <span className="slider-endpoint">T+0h (Initial Step)</span>
          <span className="slider-endpoint-center">Synchronized with Map, Cards & Timeline</span>
          <span className="slider-endpoint">T+71h (Final Step)</span>
        </div>
      </div>
    </section>
  );
};
