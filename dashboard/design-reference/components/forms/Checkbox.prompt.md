Checkbox with blue fill + white check when on. `onChange` receives the boolean, not the event.

```jsx
<Checkbox checked={agree} onChange={setAgree} label="Require human review" />
```
