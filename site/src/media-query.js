// Подписка существует только пока компонент подключён к документу.
export class MediaQueryController {
  constructor(host, query, onChange, match = query => matchMedia(query)) {
    this.host = host;
    this.media = match(query);
    this.onChange = () => { onChange(this.matches); host.requestUpdate(); };
    host.addController(this);
  }
  get matches() { return this.media.matches; }
  hostConnected() { this.media.addEventListener("change", this.onChange); }
  hostDisconnected() { this.media.removeEventListener("change", this.onChange); }
}
