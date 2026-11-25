Underline tabs with blue active indicator and optional count pills.

```jsx
<Tabs
  tabs={[
    { value: 'checks', label: 'Checks', count: 12 },
    { value: 'artifacts', label: 'Artifacts', count: 3 },
    { value: 'log', label: 'Log' },
  ]}
  value={tab}
  onChange={setTab}
/>
```
