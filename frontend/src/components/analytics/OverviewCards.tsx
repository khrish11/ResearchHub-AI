import type { GlobalAnalytics as GlobalStats } from '../../types/api';
import { BarChart3, Database, TrendingUp, Clock, AlertTriangle, XCircle, Zap, type LucideIcon } from 'lucide-react';
import { motion } from 'framer-motion';

// Formatters
const formatNumber = (num: number) => new Intl.NumberFormat('en-US').format(num);
const formatPct = (num: number | undefined) => `${((num || 0) * 100).toFixed(1)}%`;
const formatMs = (ms: number | undefined) => `${(ms || 0).toFixed(0)} ms`;

interface StatCardProps {
  label: string;
  value: string | number;
  subValue?: string;
  icon: LucideIcon;
  trend?: 'up' | 'down' | 'neutral';
  color: string;
  delay?: number;
}

function StatCard({ label, value, subValue, icon: Icon, trend, color, delay = 0 }: StatCardProps) {
  return (
    <motion.div 
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay, duration: 0.4 }}
      className="bg-white/5 dark:bg-slate-800/50 backdrop-blur-sm border border-white/10 rounded-xl p-5 hover:bg-white/10 transition-colors cursor-pointer group"
    >
      <div className="flex justify-between items-start mb-4">
        <div className={`p-2.5 rounded-lg ${color} bg-opacity-20`}>
          <Icon className={color.replace('bg-', 'text-')} size={20} />
        </div>
        {trend && (
          <div className="flex items-center gap-1 text-xs font-medium px-2 py-1 rounded-full bg-white/5 text-slate-400">
            {trend === 'up' && <TrendingUp size={12} className="text-green-400" />}
            {trend === 'down' && <TrendingUp size={12} className="text-red-400" />}
          </div>
        )}
      </div>
      <div>
        <p className="text-3xl font-bold text-slate-100 tracking-tight group-hover:text-indigo-400 transition-colors">{value}</p>
        <p className="text-sm text-slate-400 mt-1 font-medium">{label}</p>
        {subValue && <p className="text-xs text-slate-500 mt-1 font-mono">{subValue}</p>}
      </div>
    </motion.div>
  );
}

interface OverviewCardsProps {
  global: GlobalStats | null;
  loading: boolean;
}

export default function OverviewCards({ global, loading }: OverviewCardsProps) {
  if (loading || !global) {
    return (
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {[1, 2, 3, 4].map(i => (
          <div key={i} className="animate-pulse bg-white/5 border border-white/10 rounded-xl h-36" />
        ))}
      </div>
    );
  }

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
      <StatCard 
        label="Total Queries" 
        value={formatNumber(global.total_queries)} 
        icon={BarChart3} 
        trend="up"
        color="bg-indigo-500"
        delay={0.1}
      />
      <StatCard 
        label="Success Rate" 
        value={formatPct(1 - global.error_rate)} 
        subValue={`${global.error_count} errors`}
        icon={global.error_rate > 0.05 ? AlertTriangle : global.error_rate > 0.1 ? XCircle : Zap}
        color={global.error_rate > 0.05 ? "bg-amber-500" : "bg-emerald-500"}
        delay={0.2}
      />
      <StatCard 
        label="Avg Latency" 
        value={formatMs(global.avg_response_time_ms)} 
        icon={Clock} 
        trend="down"
        color="bg-purple-500"
        delay={0.3}
      />
      <StatCard 
        label="Cache Hit Rate" 
        value={formatPct(global.cache_hit_rate)}
        subValue={`${formatNumber(global.cache_hits)} hits`}
        icon={Database} 
        color="bg-cyan-500"
        delay={0.4}
      />
    </div>
  );
}
