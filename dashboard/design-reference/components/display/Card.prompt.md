Frosted glass panel; the base surface of every DCT view. Only set `interactive` when the card navigates somewhere.

```jsx
<Card title="Active agents" subtitle="4 running" action={<Badge status="running">Live</Badge>}>
  …content…
</Card>
<Card interactive onClick={open}>…</Card>
```
