Radio with blue dot when selected. `onChange` receives the radio's `value`.

```jsx
<Radio name="mode" value="auto" checked={mode === 'auto'} onChange={setMode} label="Auto-merge on pass" />
<Radio name="mode" value="manual" checked={mode === 'manual'} onChange={setMode} label="Always require review" />
```
