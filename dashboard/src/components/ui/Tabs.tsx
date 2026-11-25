'use client';

import { useState } from 'react';
import type { CSSProperties } from 'react';

type TabItem = string | { value: string; label: string; count?: number };

interface TabsProps {
  tabs: TabItem[];
  /** Controlled value; omit for uncontrolled with defaultValue. */
  value?: string;
  defaultValue?: string;
  onChange?: (value: string) => void;
  className?: string;
  style?: CSSProperties;
}

function normalize(t: TabItem) {
  return typeof t === 'string' ? { value: t, label: t, count: undefined } : t;
}

/** Underline tabs for switching panel views. */
export function Tabs({ tabs, value, defaultValue, onChange, className, style }: TabsProps) {
  const first = tabs[0] ? normalize(tabs[0]).value : undefined;
  const [internal, setInternal] = useState(defaultValue ?? first);
  const active = value !== undefined ? value : internal;

  const select = (v: string) => {
    if (value === undefined) setInternal(v);
    onChange?.(v);
  };

  return (
    <div className={['dct-tabs', className].filter(Boolean).join(' ')} style={style} role="tablist">
      {tabs.map((t) => {
        const tab = normalize(t);
        const isActive = tab.value === active;
        return (
          <button
            key={tab.value}
            type="button"
            role="tab"
            aria-selected={isActive}
            className={`dct-tabs__tab${isActive ? ' dct-tabs__tab--active' : ''}`}
            onClick={() => select(tab.value)}
          >
            {tab.label}
            {tab.count !== undefined ? <span className="dct-tabs__count">{tab.count}</span> : null}
          </button>
        );
      })}
    </div>
  );
}
