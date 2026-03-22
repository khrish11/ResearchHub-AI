import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { TimeseriesPoint } from '../../types/api';
import { motion } from 'framer-motion';

// Custom Tooltip
const CustomTooltip = ({ active, payload, label }: any) => {
  if (active && payload && payload.length) {
    return (
      <div className="bg-slate-800 border border-slate-700/50 p-3 rounded-lg shadow-xl backdrop-blur-md">
        <p className="text-slate-300 text-sm font-medium mb-2">{label}</p>
        {payload.map((entry: any, index: number) => (
          <div key={index} className="flex items-center gap-2 text-sm justify-between w-32">
            <span style={{ color: entry.color }}>{entry.name}:</span>
            <span className="font-mono font-medium text-slate-100">{entry.value}</span>
          </div>
        ))}
      </div>
    );
  }
  return null;
};

interface TimeseriesChartProps {
  timeseries: TimeseriesPoint[];
  loading: boolean;
}

export default function TimeseriesChart({ timeseries, loading }: TimeseriesChartProps) {
  if (loading || timeseries.length === 0) {
    return (
      <div className="h-[350px] w-full animate-pulse bg-white/5 border border-white/10 rounded-xl flex items-center justify-center text-slate-500 text-sm">
        {loading ? 'Loading chart data...' : 'No timeseries data'}
      </div>
    );
  }

  // Format data
  const chartData = timeseries.map(pt => {
    // Keep 'YYYY-MM-DD HH' format shorter for x-axis
    const dateStr = pt.hour.split(' ')[1] || pt.hour;
    return {
      time: dateStr + ':00',
      'Queries': pt.query_count,
      'Cache Hits': pt.cache_hits,
      'Errors': pt.error_count
    };
  });

  return (
    <motion.div 
      initial={{ opacity: 0, scale: 0.98 }}
      animate={{ opacity: 1, scale: 1 }}
      className="bg-white/5 dark:bg-slate-800/50 backdrop-blur-sm border border-white/10 rounded-xl p-6 h-[350px]"
    >
      <h3 className="text-sm font-semibold text-slate-300 mb-6">Traffic & Performance (Hourly)</h3>
      <div className="h-[260px] w-full">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={chartData} margin={{ top: 5, right: 10, left: -20, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#ffffff10" vertical={false} />
            <XAxis 
              dataKey="time" 
              stroke="#94a3b8" 
              fontSize={11}
              tickLine={false}
              axisLine={false}
              minTickGap={30}
            />
            <YAxis 
              stroke="#94a3b8" 
              fontSize={11}
              tickLine={false}
              axisLine={false}
              tickFormatter={(value) => value >= 1000 ? `${(value/1000).toFixed(1)}k` : value}
            />
            <Tooltip content={<CustomTooltip />} />
            <Line 
              type="monotone" 
              dataKey="Queries" 
              stroke="#6366f1" 
              strokeWidth={2}
              dot={false}
              activeDot={{ r: 4, fill: '#6366f1', stroke: '#fff', strokeWidth: 2 }}
            />
            <Line 
              type="monotone" 
              dataKey="Cache Hits" 
              stroke="#06b6d4" 
              strokeWidth={2}
              dot={false}
            />
            <Line 
              type="monotone" 
              dataKey="Errors" 
              stroke="#ef4444" 
              strokeWidth={2}
              dot={false}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </motion.div>
  );
}
