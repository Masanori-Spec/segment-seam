export const MAX_FILE_BYTES = 4 * 1024 * 1024;
export const MAX_POINTS = 20000;
export function fileProblem(file) {
  if (!file) return 'missing';
  if (!/\.gpx$/i.test(file.name || '')) return 'extension';
  if (!Number.isFinite(file.size) || file.size <= 0) return 'empty';
  if (file.size > MAX_FILE_BYTES) return 'large';
  return '';
}
export function formatBytes(bytes) {
  return bytes < 1024 * 1024 ? `${Math.max(1, Math.round(bytes / 1024))} KiB` : `${(bytes / (1024 * 1024)).toFixed(1)} MiB`;
}
const positive = n => Number.isInteger(n) && n > 0;
const nonnegative = n => Number.isInteger(n) && n >= 0;
const trackValid = track => track && positive(track.index) && track.index <= 256 && typeof track.name === 'string' && nonnegative(track.points) && track.points <= MAX_POINTS && nonnegative(track.segments) && track.segments <= 2000 && nonnegative(track.empty_segments) && track.empty_segments <= track.segments;
const provenanceValid = file => file && typeof file.name === 'string' && typeof file.sha256 === 'string' && /^[a-f0-9]{64}$/.test(file.sha256) && positive(file.bytes) && file.bytes <= MAX_FILE_BYTES;
const stringList = value => Array.isArray(value) && value.every(item => typeof item === 'string');
export function validInventory(value) {
  return Boolean(value?.kind === 'inventory' && value.limits?.max_bytes === MAX_FILE_BYTES && value.limits?.max_points === MAX_POINTS && ['before', 'after'].every(side => {
    const item = value[side];
    return provenanceValid(item) && Array.isArray(item.tracks) && item.tracks.length <= 256 && item.tracks.every(trackValid) &&
      item.tracks.every((track, index) => track.index === index + 1) && nonnegative(item.waypoints) && nonnegative(item.routes) &&
      item.tracks.reduce((sum, track) => sum + track.points, 0) <= MAX_POINTS;
  }));
}
export function canCompare(inventory, beforeIndex, afterIndex, confirmed) {
  return Boolean(validInventory(inventory) && confirmed === true && positive(Number(beforeIndex)) && positive(Number(afterIndex)) &&
    inventory.before.tracks.some(track => track.index === Number(beforeIndex)) && inventory.after.tracks.some(track => track.index === Number(afterIndex)));
}
const rawValid = field => field && ['absent', 'raw'].includes(field.state) && (field.state !== 'raw' || typeof field.text === 'string');
const pointValid = point => point && positive(point.index) && typeof point.lat === 'string' && typeof point.lon === 'string' && rawValid(point.elevation) && rawValid(point.time);
const nonnegativeDistance = value => Number.isFinite(value) && value >= 0;
const near = (left, right) => Math.abs(left - right) <= 1e-7 * Math.max(1, Math.abs(left), Math.abs(right));
export function validReport(report) {
  if (!report || report.kind !== 'comparison' || report.schema !== 'segment-seam/1' || !['complete', 'unsupported'].includes(report.status) ||
      !stringList(report.reasons) || !stringList(report.scope) || !report.scope.length || !Array.isArray(report.seams) || report.seams.length > 2000 ||
      report.witnesses_truncated !== false || typeof report.metadata_note !== 'string' ||
      !['before', 'after'].every(side => provenanceValid(report[side]) && trackValid(report[side].track)) ||
      !report.method || typeof report.method.name !== 'string' || !report.method.name || typeof report.method.description !== 'string' || !nonnegativeDistance(report.method.radius_m) || report.method.radius_m === 0) return false;
  if (report.status === 'unsupported') return report.verdict === 'not_compared' && report.summary === null && report.seams.length === 0 && report.reasons.length > 0;
  const sum = report.summary;
  if (!sum || report.reasons.length || !positive(sum.points) || sum.points !== report.before.track.points || sum.points !== report.after.track.points ||
      report.before.track.empty_segments !== 0 || report.after.track.empty_segments !== 0 ||
      !['removed_boundaries','added_boundaries','retained_boundaries'].every(key => nonnegative(sum[key])) ||
      !['before_distance_m','after_distance_m','artificial_distance_m','disconnected_distance_m'].every(key => nonnegativeDistance(sum[key])) ||
      !Number.isFinite(sum.net_distance_change_m)) return false;
  const counts = {removed: 0, added: 0, retained: 0}, totals = {removed: 0, added: 0, retained: 0};
  let previous = 0;
  for (const seam of report.seams) {
    if (!positive(seam.left_point) || seam.left_point <= previous || seam.right_point !== seam.left_point + 1 || seam.right_point > sum.points ||
        !['removed', 'added', 'retained'].includes(seam.change) || !nonnegativeDistance(seam.distance_m) ||
        !pointValid(seam.left) || !pointValid(seam.right) || seam.left.index !== seam.left_point || seam.right.index !== seam.right_point) return false;
    for (const side of ['before','after']) {
      const pair = seam[side], boundary = side === 'before' ? seam.change !== 'added' : seam.change !== 'removed';
      if (!pair || !positive(pair.left_segment) || !positive(pair.right_segment) || pair.right_segment > report[side].track.segments || pair.right_segment !== pair.left_segment + (boundary ? 1 : 0)) return false;
    }
    previous = seam.left_point; counts[seam.change]++; totals[seam.change] += seam.distance_m;
  }
  return report.verdict === ((counts.removed || counts.added) ? 'boundaries_changed' : 'boundaries_unchanged') &&
    Object.keys(counts).every(change => counts[change] === sum[`${change}_boundaries`]) &&
    report.before.track.segments === counts.removed + counts.retained + 1 && report.after.track.segments === counts.added + counts.retained + 1 &&
    near(totals.removed, sum.artificial_distance_m) && near(totals.added, sum.disconnected_distance_m) &&
    near(sum.artificial_distance_m - sum.disconnected_distance_m, sum.net_distance_change_m) &&
    Math.abs((sum.after_distance_m - sum.before_distance_m) - sum.net_distance_change_m) <= 1e-9 * Math.max(1, sum.before_distance_m, sum.after_distance_m);
}
export function distance(value, locale = 'en') {
  return `${new Intl.NumberFormat(locale === 'ja' ? 'ja-JP' : 'en-US', {maximumFractionDigits: 2}).format(value)} m`;
}
export function bytesToBase64(bytes) {
  let data = '';
  for (let offset = 0; offset < bytes.length; offset += 0x8000) data += String.fromCharCode(...bytes.subarray(offset, offset + 0x8000));
  return btoa(data);
}
export function abortableDelay(ms, signal) {
  return new Promise((resolve, reject) => {
    if (signal.aborted) return reject(new DOMException('Aborted', 'AbortError'));
    const cancel = () => { clearTimeout(timer); reject(new DOMException('Aborted', 'AbortError')); };
    const timer = setTimeout(() => { signal.removeEventListener('abort', cancel); resolve(); }, ms);
    signal.addEventListener('abort', cancel, {once: true});
  });
}
// Start responses remain readable so cancellation can always target the server ID.
// Polls abort immediately. A new POST waits until retired starts have been cancelled.
export class JobRunner {
  constructor({fetcher = (...args) => globalThis.fetch(...args), onUpdate = () => {}, delay = abortableDelay, pollMs = 350} = {}) {
    this.fetcher = fetcher; this.onUpdate = onUpdate; this.delay = delay; this.pollMs = pollMs;
    this.generation = 0; this.current = null; this.barrier = Promise.resolve();
  }
  async cancelRemote(id) {
    const response = await this.fetcher(`api/jobs/${encodeURIComponent(id)}/cancel`, {
      method: 'POST', headers: {'Content-Type': 'application/json'}, body: '{}', keepalive: true,
    });
    if (response.status === 404) return; // Replaced or removed jobs have no live worker/artifact.
    if (!response.ok) throw new Error(`Cancel failed (${response.status})`);
    const data = await response.json();
    if (data.id !== id || data.status !== 'cancelled' || data.result !== undefined) throw new Error('Server cancellation was not confirmed');
  }
  cancel() {
    this.generation += 1;
    const old = this.current; this.current = null;
    if (!old) return this.barrier;
    old.abort.abort();
    const cleanup = (async () => {
      const id = old.id || await old.idPromise.catch(() => null);
      if (id) await this.cancelRemote(id);
    })();
    // Keep a rejected cleanup barrier: further jobs must not hide an unconfirmed cancellation.
    this.barrier = Promise.all([this.barrier, cleanup]).then(() => undefined);
    this.barrier.catch(() => {});
    return this.barrier;
  }
  async start(payload) {
    this.cancel();
    const prior = this.barrier;
    const task = {generation: this.generation, abort: new AbortController(), id: null};
    this.current = task;
    const active = () => this.current === task && this.generation === task.generation;
    task.idPromise = (async () => {
      await prior;
      if (!active()) return null;
      const response = await this.fetcher('api/jobs', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(payload)});
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || `Request failed (${response.status})`);
      if (typeof data.id !== 'string' || !data.id) throw new Error('Server returned no job ID');
      return data.id;
    })();
    try {
      const id = await task.idPromise;
      task.id = id;
      if (!active() || !id) return;
      this.onUpdate({status: 'running', id, progress: 0}, payload.mode);
      while (active()) {
        const response = await this.fetcher(`api/jobs/${encodeURIComponent(id)}`, {signal: task.abort.signal, cache: 'no-store'});
        const data = await response.json();
        if (!response.ok) throw new Error(data.error || `Request failed (${response.status})`);
        if (!active()) return;
        if (data.id !== id || !['running', 'done', 'error', 'cancelled'].includes(data.status)) throw new Error('Invalid worker response');
        if (data.status === 'done' && !(payload.mode === 'inspect' ? validInventory(data.result) : validReport(data.result))) throw new Error('Incomplete worker result');
        this.onUpdate(data, payload.mode);
        if (data.status !== 'running') return;
        await this.delay(this.pollMs, task.abort.signal);
      }
    } catch (error) {
      if (active() && error.name !== 'AbortError') this.onUpdate({status: 'error', error: error.message}, payload.mode);
    }
  }
}
