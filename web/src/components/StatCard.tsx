interface StatCardProps {
  label: string;
  value: number | string;
  subtext?: string;
}

export default function StatCard({ label, value, subtext }: StatCardProps) {
  return (
    <div className="rounded-lg border border-surface-200 bg-white p-4 shadow-sm">
      <p className="text-xs font-medium uppercase tracking-wider text-surface-500">{label}</p>
      <p className="mt-1 text-2xl font-semibold tabular-nums text-surface-900">{value}</p>
      {subtext && <p className="mt-1 text-xs text-surface-500">{subtext}</p>}
    </div>
  );
}
