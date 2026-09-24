"use client";

import { useEffect, useState } from "react";
import { clamp } from "@/lib/format";

interface ProgressBarProps {
  percent: number;
  target?: number;
  current?: number;
}

export default function ProgressBar({ percent, target, current }: ProgressBarProps) {
  const [width, setWidth] = useState(0);

  useEffect(() => {
    const t = setTimeout(() => setWidth(clamp(percent, 0, 100)), 100);
    return () => clearTimeout(t);
  }, [percent]);

  return (
    <div className="w-full">
      <div className="mb-1 flex items-center justify-between text-sm">
        <span className="font-medium text-surface-700">Overall Progress</span>
        <span className="tabular-nums text-surface-600">
          {current !== undefined && target !== undefined
            ? `${current.toLocaleString()} / ${target.toLocaleString()} (${percent.toFixed(1)}%)`
            : `${percent.toFixed(1)}%`}
        </span>
      </div>
      <div className="h-3 w-full overflow-hidden rounded-full bg-surface-200">
        <div
          className="h-full rounded-full bg-surface-800 transition-all duration-700 ease-out"
          style={{ width: `${width}%` }}
        />
      </div>
    </div>
  );
}
