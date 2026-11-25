Modal on a heavy-blur scrim; use for confirmations that gate irreversible actions (approve, reject).

```jsx
<Dialog
  open={open}
  onClose={close}
  title="Reject this run?"
  subtitle="run_8f3ka92 · deploy-service"
  footer={<>
    <Button variant="ghost" onClick={close}>Cancel</Button>
    <Button variant="danger" icon="x" onClick={reject}>Reject run</Button>
  </>}
>
  The agent's changes will be discarded. This can't be undone.
</Dialog>
```
