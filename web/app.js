import {MAX_FILE_BYTES, fileProblem, formatBytes, canCompare, bytesToBase64, distance, JobRunner} from './model.js';
const backendJapanese = new Map([
  ['Only the explicitly selected before/after tracks are compared.','明示的に選択した変更前・変更後のトラックだけを比較します。'],
  ['Point order and normalized XML point content must remain unchanged; no near matching.','点の順序と正規化した XML の点内容が同じである必要があります。近似マッチングは行いません。'],
  ['Only segment boundaries and horizontal spherical edge distances are reviewed.','確認対象はセグメント境界と、球面上の水平な辺の距離だけです。'],
  ['Other tracks, waypoints, routes, and track/segment/file metadata are not compared.','他のトラック、ウェイポイント、ルート、トラック・セグメント・ファイルのメタデータは比較しません。'],
  ['No conclusion about full GPX equivalence, recording truth, navigation, or route safety.','GPX 全体の同等性、記録の真実性、ナビゲーション、ルートの安全性について結論を出しません。'],
  ['Selected tracks must contain at least one point.','選択したトラックには、少なくとも1点が必要です。'],
  ['Empty segments are unsupported; no boundary was silently collapsed.','空のセグメントは対応範囲外です。境界を黙って統合することはありません。'],
  ['Selected point counts differ; no near matching or interpolation was attempted.','選択したトラックの点数が異なります。近似マッチングや補間は行っていません。'],
  ['More than 2,000 unique boundary witnesses; no partial success or truncated verdict is emitted.','境界の証拠が2,000件を超えています。一部だけを使った成功判定や省略した判定は行いません。'],
  ['Track, segment and file metadata, other tracks, routes and waypoints are not compared. Time and elevation are preserved raw text, not validated or used in distance. Reports contain exact selected point coordinates; keep them private.','トラック・セグメント・ファイルのメタデータ、他のトラック、ルート、ウェイポイントは比較しません。時刻と標高は原文を保持し、妥当性の検証や距離計算には使いません。レポートには選択した点の正確な座標が含まれるため、公開には注意してください。'],
  ['Haversine central angle on a sphere with radius 6371008.8 m, using a directly computed complementary half-angle near antipodes for numerical stability. Horizontal only; not WGS84 ellipsoidal or elevation-aware. Numerical estimates, not measured travel.','半径 6371008.8 m の球面上の Haversine 中心角で計算します。対蹠点付近では相補半角を直接計算して数値を安定化します。水平距離のみで、WGS84 楕円体や標高差は考慮しません。数値上の推定であり、実測の移動距離ではありません。'],
]);
function backendText(value) {
  if(state.lang!=='ja')return value;
  if(backendJapanese.has(value))return backendJapanese.get(value);
  const mismatch=value.match(/^Normalized XML point content differs at point (\d+); no near matching was attempted\.$/);
  if(mismatch)return `点 ${mismatch[1]} の正規化した XML 内容が異なります。近似マッチングは行っていません。`;
  return `技術詳細（原文）: ${value}`;
}
const $ = id => document.getElementById(id);
const copy = {
  en: {
    skip:'Skip to workbench',local:'LOCAL WORKBENCH',eyebrow:'THE GPX BOUNDARY EVIDENCE WORKBENCH',heroFirst:'Same points.',heroSecond:'Different connections.',intro:'A track can keep every point and still gain a connecting edge. See exactly which segment boundaries changed between two GPX files.',tagLocal:'Local processing',tagExact:'Exact point witnesses',tagNoMap:'No map requests',diagramTitle:'A BOUNDARY, REMOVED',before:'Before',after:'After',diagramLegend:'A newly connected edge',diagramFoot:'Schematic only. Not a geographic map.',scopeLead:'One logical track. An unchanged point sequence.',scopeBody:'Choose one track from each file and confirm they represent the same logical track. This review checks segment boundaries only, not full GPX equivalence or navigation safety.',stepOne:'01 / INPUTS',inputTitle:'Bring both versions',demo:'Try a synthetic example ↗',beforeFile:'Before GPX',afterFile:'After GPX',beforeHint:'Your original segmentation',afterHint:'The version you want to check',chooseGPX:'Choose a GPX file',fileHint:'or drop it here · max 4 MiB',limits:'4 MiB per file · 20,000 points per file\nProcessed by a cancellable local worker',inspect:'Inspect tracks →',stepTwo:'02 / EXPLICIT TRACK PAIR',trackTitle:'Choose what belongs together',inspected:'Inputs inspected',beforeTrack:'Before track · 1-based index',afterTrack:'After track · 1-based index',confirm:'I confirm these are the same logical track in the before and after files.',trackScope:'Other tracks, routes, waypoints, and document metadata are outside this review.',compare:'Review segment seams →',cancel:'Cancel',stepThree:'03 / SCOPED EVIDENCE',download:'Download evidence ZIP ↓',emptyTitle:'The space between points matters.',emptyText:'Inspect your files, select a track pair, then review the boundary evidence here.',footerSub:'A narrow question. Inspectable evidence.',footer:'Distance: spherical horizontal Haversine, not ellipsoidal or elevation-aware. Raw times are displayed as supplied, never interpreted as travel duration.',restart:'Clear & restart',swap:'Swap before and after files',progress:'Worker progress',initial:'Choose both GPX files. Their contents stay on the computer running this local server.',ready:'Both files are ready. Inspect tracks before selecting a pair.',reading:'Reading GPX bytes…',demoLoading:'Loading the synthetic example…',inspecting:'Inspecting both files in the local worker…',comparing:'Reviewing the selected track pair in the local worker…',inspectDone:'Tracks inspected. Explicitly choose a before and after track, then confirm the pair.',complete:'Scoped boundary review complete. Read the scope and individual witnesses below.',unsupported:'This pair cannot be compared within the supported scope. Read the reasons below.',cancelled:'Cancelled. Any previous result and download have been cleared.',failed:'The worker did not complete. No result is available.',cancelFailed:'Server cancellation could not be confirmed. Restart the local server before starting another job.',missing:'Choose a GPX file.',extension:'Choose a file with a .gpx extension.',empty:'This file is empty or cannot be read.',large:'This file exceeds the 4 MiB limit.',readFailed:'This file could not be read.',chooseTrack:'Choose a track explicitly…',noTracks:'No tracks found',unnamed:'Unnamed track',track:'Track',points:'points',segments:'segments',emptySegments:'empty segments',routes:'routes',waypoints:'waypoints',outside:'outside selected-track scope',changedTitle:'The boundary pattern changed.',unchangedTitle:'The boundary pattern is unchanged.',unsupportedTitle:'Outside the supported comparison.',scopedSubtitle:'Selected tracks only · point indices are 1-based · no equivalence or safety claim',metricArtificial:'Newly connected distance',metricArtificialDetail:'Across removed boundaries',metricRemoved:'Removed boundaries',metricRemovedDetail:'New edges in the after track',metricAdded:'Added boundaries',metricAddedDetail:'Edges disconnected in the after track',metricRetained:'Retained boundaries',metricRetainedDetail:'Still disconnected in both tracks',beforeDistance:'Before connected distance',afterDistance:'After connected distance',disconnected:'Newly disconnected distance',net:'Net distance change',matched:'Point sequence checked',scopeNote:'This is a scoped segment-boundary review. It does not establish full GPX equivalence, route correctness, or navigation safety.',method:'Method',radius:'sphere radius',unsupportedLead:'No boundary metrics were calculated.',unsupportedText:'This is an unsupported comparison, not evidence that the files are equivalent. The ZIP preserves the reasons.',witnessTitle:'Boundary witnesses',witnessIntro:'Every boundary in either selected track · expand for raw point evidence',all:'All',removed:'Removed',added:'Added',retained:'Retained',point:'Point',raw:'raw',absent:'Not supplied',lat:'Latitude',lon:'Longitude',ele:'Elevation',time:'Time',removedExplain:'This boundary disappeared. These two points now form a newly connected edge in the after track.',addedExplain:'A new boundary disconnects these two points in the after track.',retainedExplain:'This boundary remains. These two points are disconnected in both tracks.',segmentPair:'segment pair',noSeams:'There are no segment boundaries between adjacent points in either selected track.',noFilter:'No witnesses match this filter.',previous:'← Previous',next:'Next →',page:'Page',of:'of',provenance:'Scope, method & source fingerprints',sha:'SHA-256',witnessWarning:'The report says witnesses were truncated. Download the packet and review this limitation.',demoInvalid:'The demo response was incomplete.',serverDetail:'Worker detail: ',synthetic:'synthetic example',errorRetry:'Check the file and try again.',
  },
  ja: {
    skip:'ワークベンチへ移動',local:'ローカルで処理',eyebrow:'GPX セグメント境界のエビデンス',heroFirst:'点は同じ。',heroSecond:'つながりは違う。',intro:'すべての点が残っていても、セグメント境界が消えると新しい接続が生まれます。2つの GPX ファイルの境界差分を、点の証拠から確認します。',tagLocal:'ローカル処理',tagExact:'点ごとの原文証拠',tagNoMap:'地図通信なし',diagramTitle:'境界が1つ消えた例',before:'変更前',after:'変更後',diagramLegend:'新しく接続された辺',diagramFoot:'境界の模式図です。地理的な地図ではありません。',scopeLead:'同じ論理トラック、変わらない点の並び。',scopeBody:'各ファイルから1つずつトラックを選び、同じ論理トラックであることを確認します。確認対象はセグメント境界のみです。GPX 全体の同等性やナビゲーションの安全性は判定しません。',stepOne:'01 / ファイル',inputTitle:'変更前と変更後を用意',demo:'架空のサンプルを試す ↗',beforeFile:'変更前の GPX',afterFile:'変更後の GPX',beforeHint:'元のセグメント構成',afterHint:'確認したいバージョン',chooseGPX:'GPX ファイルを選択',fileHint:'またはここにドロップ · 最大 4 MiB',limits:'各ファイル 4 MiB・20,000点まで\nキャンセル可能なローカルワーカーで処理',inspect:'トラックを確認 →',stepTwo:'02 / トラックを明示的に選択',trackTitle:'対応するトラックを選ぶ',inspected:'ファイル確認済み',beforeTrack:'変更前のトラック · 1始まりの番号',afterTrack:'変更後のトラック · 1始まりの番号',confirm:'選択した変更前・変更後のトラックが、同じ論理トラックであることを確認しました。',trackScope:'他のトラック、ルート、ウェイポイント、文書メタデータは確認対象外です。',compare:'セグメント境界を比較 →',cancel:'キャンセル',stepThree:'03 / 限定範囲のエビデンス',download:'エビデンス ZIP を保存 ↓',emptyTitle:'点と点の間に、違いがある。',emptyText:'ファイルを確認し、対応するトラックを選ぶと、ここに境界の証拠が表示されます。',footerSub:'狭い問いを、確認できる証拠に。',footer:'距離は球面の水平 Haversine 距離です。楕円体や標高差は考慮しません。時刻は原文のまま表示し、移動時間に変換しません。',restart:'クリアしてやり直す',swap:'変更前と変更後のファイルを入れ替える',progress:'ワーカーの進行状況',initial:'2つの GPX ファイルを選択してください。内容はこのローカルサーバーを実行しているコンピューター内で処理します。',ready:'ファイルを用意できました。まずトラックを確認してください。',reading:'GPX のデータを読み込み中…',demoLoading:'架空のサンプルを読み込み中…',inspecting:'ローカルワーカーで両方のファイルを確認中…',comparing:'ローカルワーカーで選択したトラックを比較中…',inspectDone:'ファイルを確認しました。変更前・変更後のトラックを明示的に選択して、対応関係を確認してください。',complete:'限定範囲の境界比較が完了しました。対象範囲と各点の証拠を確認してください。',unsupported:'この組み合わせは対応範囲内で比較できません。以下の理由を確認してください。',cancelled:'キャンセルしました。以前の結果とダウンロードをクリアしました。',failed:'処理が完了しませんでした。結果はありません。',cancelFailed:'サーバー側のキャンセルを確認できませんでした。次の処理の前にローカルサーバーを再起動してください。',missing:'GPX ファイルを選択してください。',extension:'拡張子 .gpx のファイルを選択してください。',empty:'ファイルが空か、読み込めません。',large:'ファイルが 4 MiB の上限を超えています。',readFailed:'ファイルを読み込めませんでした。',chooseTrack:'トラックを明示的に選択…',noTracks:'トラックがありません',unnamed:'名称なし',track:'トラック',points:'点',segments:'セグメント',emptySegments:'空セグメント',routes:'ルート',waypoints:'ウェイポイント',outside:'選択トラックの対象範囲外',changedTitle:'境界の構成が変わりました。',unchangedTitle:'境界の構成は同じです。',unsupportedTitle:'対応する比較範囲外です。',scopedSubtitle:'選択トラックのみ · 点番号は1始まり · 同等性・安全性の判定なし',metricArtificial:'新しく接続された距離',metricArtificialDetail:'消えた境界をまたぐ距離',metricRemoved:'消えた境界',metricRemovedDetail:'変更後に新しく接続された辺',metricAdded:'追加された境界',metricAddedDetail:'変更後に接続が切れた辺',metricRetained:'維持された境界',metricRetainedDetail:'両方で接続されていない箇所',beforeDistance:'変更前の接続距離',afterDistance:'変更後の接続距離',disconnected:'新しく切断された距離',net:'接続距離の差',matched:'点の並びを確認',scopeNote:'これはセグメント境界に限定した比較です。GPX 全体の同等性、ルートの正しさ、ナビゲーションの安全性を保証しません。',method:'距離の計算法',radius:'球の半径',unsupportedLead:'境界の指標は計算していません。',unsupportedText:'対応範囲外という結果であり、ファイルが同等である証拠ではありません。ZIP に理由が記録されています。',witnessTitle:'境界の証拠',witnessIntro:'いずれかのトラックにある全境界 · 展開して点の原文を確認',all:'すべて',removed:'消失',added:'追加',retained:'維持',point:'点',raw:'原文',absent:'記載なし',lat:'緯度',lon:'経度',ele:'標高',time:'時刻',removedExplain:'この境界は消えました。2つの点は変更後のトラックで新しく接続されています。',addedExplain:'追加された境界により、変更後のトラックでは2つの点が接続されていません。',retainedExplain:'この境界は維持されています。どちらのトラックでも2つの点は接続されていません。',segmentPair:'セグメント番号',noSeams:'どちらの選択トラックにも、隣接する点の間にセグメント境界はありません。',noFilter:'この条件に一致する証拠はありません。',previous:'← 前へ',next:'次へ →',page:'ページ',of:'/',provenance:'対象範囲・計算法・ファイルの指紋',sha:'SHA-256',witnessWarning:'レポートでは証拠が省略されていると報告されています。ZIP と制約を確認してください。',demoInvalid:'サンプルの応答が不完全でした。',serverDetail:'ワーカーの詳細: ',synthetic:'架空のサンプル',errorRetry:'ファイルを確認して、もう一度お試しください。',
  },
};
const state = {lang:'en', files:{before:null,after:null}, loading:{before:false,after:false}, errors:{before:'',after:''}, inventory:null, report:null, reportId:null, beforeTrack:'', afterTrack:'', confirmed:false, busy:false, mode:null, status:'initial', error:'', fatal:false, progress:null, filter:'all', page:0};
const fileTokens = {before:0,after:0};
let revision=0, demoAbort=null;
const t = key => copy[state.lang][key] || key;
const node = (tag, className, text) => { const element=document.createElement(tag); if(className) element.className=className; if(text!==undefined) element.textContent=String(text); return element; };
const text = (id,value) => { $(id).textContent=value; };
const ready = () => state.files.before && state.files.after && !state.loading.before && !state.loading.after;
const runner = new JobRunner({onUpdate(data, mode) {
  if(data.status==='running') {state.progress=typeof data.progress==='number'?data.progress:null;renderControls();return;}
  state.busy=false; state.progress=null;
  if(data.status==='done') {
    if(mode==='inspect') {state.inventory=data.result;state.beforeTrack='';state.afterTrack='';state.confirmed=false;state.status='inspectDone';}
    else {state.report=data.result;state.reportId=data.id;state.filter='all';state.page=0;state.status=data.result.status==='unsupported'?'unsupported':'complete';}
  } else {state.status=data.status==='cancelled'?'cancelled':'failed';state.error=data.error||'';}
  render();
}});
function invalidate(clearInventory=false) {
  const current=++revision;
  if(demoAbort) {demoAbort.abort();demoAbort=null;}
  state.busy=false;state.progress=null;state.report=null;state.reportId=null;state.error='';
  if(clearInventory){state.inventory=null;state.beforeTrack='';state.afterTrack='';state.confirmed=false;}
  state.status=state.inventory?'inspectDone':ready()?'ready':'initial';
  // Hide the old download synchronously, even while server cancellation is pending.
  $('download-link').removeAttribute('href');$('report-section').hidden=true;$('empty-state').hidden=false;
  runner.cancel().catch(error=>{if(current===revision){state.fatal=true;state.status='cancelFailed';state.error=error.message;render();}});
}
function renderControls() {
  const reading=state.loading.before||state.loading.after;
  $('inspect-button').disabled=!ready()||state.busy||state.fatal;
  $('compare-button').disabled=state.busy||state.fatal||!canCompare(state.inventory,state.beforeTrack,state.afterTrack,state.confirmed);
  $('swap-button').disabled=!ready()||reading;
  $('demo-button').disabled=state.mode==='demo'&&state.busy;
  $('cancel-button').hidden=!state.busy;
  $('status-region').classList.toggle('busy',state.busy);
  text('status-icon',state.busy?'◌':state.status==='complete'?'✓':state.status==='failed'||state.fatal?'!':'○');
  text('status-text',t(reading?'reading':state.status));
  $('progress-wrap').hidden=!state.busy||state.mode==='demo';
  if(state.progress===null) $('job-progress').removeAttribute('value'); else $('job-progress').value=Math.max(0,Math.min(100,state.progress));
  $('error-region').hidden=!state.error;
  text('error-region',state.error?t('serverDetail')+state.error:'');
  $('same-track').checked=state.confirmed;
  // Changes remain available during compare; they invalidate the in-flight report.
  $('same-track').disabled=!state.inventory;
}
function renderFiles(){for(const side of ['before','after']){
  const file=state.files[side];text(`${side}-name`,file?file.name:t('chooseGPX'));text(`${side}-detail`,state.loading[side]?t('reading'):file?`${formatBytes(file.size)}${file.synthetic?' · '+t('synthetic'):''}`:t('fileHint'));
  $(`${side}-drop`).classList.toggle('loaded',Boolean(file));$(`${side}-error`).hidden=!state.errors[side];text(`${side}-error`,state.errors[side]?t(state.errors[side]):'');
}}
function renderTracks(){
  $('track-section').hidden=!state.inventory;
  if(!state.inventory)return;
  for(const side of ['before','after']) {
    const inv=state.inventory[side], select=$(`${side}-track`);select.replaceChildren();
    const placeholder=node('option','',t(inv.tracks.length?'chooseTrack':'noTracks'));placeholder.value='';select.append(placeholder);
    for(const track of inv.tracks) {const option=node('option','',`${track.index} · ${track.name||t('unnamed')} · ${track.points} ${t('points')} / ${track.segments} ${t('segments')}`);option.value=String(track.index);select.append(option);}
    select.value=state[`${side}Track`];select.disabled=!inv.tracks.length;
    const chosen=inv.tracks.find(track=>String(track.index)===state[`${side}Track`]);
    text(`${side}-inventory`,`${inv.tracks.length} ${t('track')} · ${inv.routes??0} ${t('routes')} / ${inv.waypoints??0} ${t('waypoints')} (${t('outside')})${chosen?` · ${chosen.empty_segments} ${t('emptySegments')}`:''}`);
  }
}
function metric(label,value,detail,warn=false){const card=node('div',`metric${warn?' warn':''}`);card.append(node('p','metric-label',t(label)),node('p','metric-value',value),node('p','metric-detail',t(detail)));return card;}
function pointCard(point){const card=node('div','point-card');card.append(node('h4','',`${t('point')} ${point.index} · ${t('raw')}`));const dl=node('dl');for(const [label,value] of [['lat',point.lat],['lon',point.lon],['ele',point.elevation.state==='absent'?t('absent'):JSON.stringify(point.elevation.text)],['time',point.time.state==='absent'?t('absent'):JSON.stringify(point.time.text)]])dl.append(node('dt','',t(label)),node('dd','',value));card.append(dl);return card;}
function seamRow(seam){
  const row=node('details','seam-row');const summary=node('summary');summary.append(node('span',`change-badge change-${seam.change}`,t(seam.change)),node('span','seam-points',`${t('point')} ${seam.left_point} → ${seam.right_point}`),node('span','seam-distance',distance(seam.distance_m,state.lang)));row.append(summary);
  const body=node('div','witness-body');body.append(node('p','seam-explanation',t(`${seam.change}Explain`)));const points=node('div','witness-grid');points.append(pointCard(seam.left),pointCard(seam.right));body.append(points,node('p','raw-hint',state.lang==='ja'?'標高・時刻の原文は JSON 文字列で表示します。空文字や空白も区別できます。':'Raw elevation and time use JSON string notation so empty text and whitespace stay distinguishable.'),node('p','segment-change',`${t('segmentPair')} · ${t('before')}: ${seam.before.left_segment} → ${seam.before.right_segment} · ${t('after')}: ${seam.after.left_segment} → ${seam.after.right_segment}`));row.append(body);return row;
}
function evidence(report){
  const panel=node('section','evidence-panel');panel.setAttribute('aria-label',t('witnessTitle'));
  const heading=node('div','evidence-heading'), title=node('div');title.append(node('h3','',t('witnessTitle')),node('p','',t('witnessIntro')));heading.append(title);const filters=node('div','filters');filters.setAttribute('role','group');filters.setAttribute('aria-label',t('witnessTitle'));
  for(const value of ['all','removed','added','retained']) {const count=value==='all'?report.seams.length:report.seams.filter(seam=>seam.change===value).length;const button=node('button','filter-button',`${t(value)} ${count}`);button.type='button';button.dataset.filter=value;button.setAttribute('aria-pressed',String(state.filter===value));button.addEventListener('click',()=>{state.filter=value;state.page=0;renderReport();$('report-body').querySelector(`[data-filter="${value}"]`).focus();});filters.append(button);}
  heading.append(filters);panel.append(heading);const rows=report.seams.filter(seam=>state.filter==='all'||seam.change===state.filter), pages=Math.max(1,Math.ceil(rows.length/30));state.page=Math.min(state.page,pages-1);
  if(!rows.length)panel.append(node('p','evidence-empty',t(report.seams.length?'noFilter':'noSeams')));
  for(const seam of rows.slice(state.page*30,(state.page+1)*30))panel.append(seamRow(seam));
  if(pages>1){const pagination=node('nav','pagination');pagination.setAttribute('aria-label',t('page'));const prev=node('button','',t('previous')),next=node('button','',t('next'));prev.type=next.type='button';prev.disabled=state.page===0;next.disabled=state.page===pages-1;prev.addEventListener('click',()=>{state.page--;renderReport();});next.addEventListener('click',()=>{state.page++;renderReport();});pagination.append(prev,node('span','',`${t('page')} ${state.page+1} ${t('of')} ${pages}`),next);panel.append(pagination);}
  return panel;
}
function provenance(report){
  const detail=node('details','report-provenance');detail.append(node('summary','',t('provenance')));
  const scope=node('ul');for(const item of report.scope)scope.append(node('li','',backendText(item)));detail.append(scope);
  if(report.method) detail.append(node('p','',`${t('method')}: ${report.method.name}. ${backendText(report.method.description||'')} ${t('radius')}: ${report.method.radius_m??'?'} m.`));
  if(report.metadata_note)detail.append(node('p','',backendText(report.metadata_note)));
  const grid=node('div','provenance-grid');for(const side of ['before','after']){const file=report[side], col=node('div');col.append(node('h4','',`${t(side)} · ${t('track')} ${file.track.index}`),node('p','',file.name),node('p','',`${file.track.name||t('unnamed')} · ${file.track.points} ${t('points')} · ${file.track.segments} ${t('segments')} · ${file.track.empty_segments} ${t('emptySegments')}`),node('p','',`${t('sha')}: ${file.sha256}`));grid.append(col);}detail.append(grid);return detail;
}
function renderReport(){
  const report=state.report;$('report-section').hidden=!report;$('empty-state').hidden=Boolean(report);$('report-body').replaceChildren();
  if(!report){$('download-link').removeAttribute('href');return;}
  $('download-link').href=`api/jobs/${encodeURIComponent(state.reportId)}/packet.zip`;
  text('report-title',t(report.status==='unsupported'?'unsupportedTitle':report.verdict==='boundaries_changed'?'changedTitle':'unchangedTitle'));text('report-subtitle',t('scopedSubtitle'));
  const body=$('report-body');
  if(report.status==='unsupported') {const note=node('div','result-note unsupported-note');note.append(node('h3','',t('unsupportedLead')),node('p','',t('unsupportedText')));const reasons=node('ul');for(const reason of report.reasons)reasons.append(node('li','',backendText(reason)));note.append(reasons);body.append(note);}
  else {
    const sum=report.summary, metrics=node('div','metrics-grid');metrics.append(metric('metricArtificial',distance(sum.artificial_distance_m,state.lang),'metricArtificialDetail',sum.artificial_distance_m>0),metric('metricRemoved',sum.removed_boundaries,'metricRemovedDetail'),metric('metricAdded',sum.added_boundaries,'metricAddedDetail'),metric('metricRetained',sum.retained_boundaries,'metricRetainedDetail'));body.append(metrics);
    const distances=node('div','distance-summary');for(const [key,value] of [['beforeDistance',sum.before_distance_m],['afterDistance',sum.after_distance_m],['disconnected',sum.disconnected_distance_m],['net',sum.net_distance_change_m]]){const span=node('span','',t(key)+': ');span.append(node('strong','',distance(value,state.lang)));distances.append(span);}body.append(distances);
    const note=node('div','result-note');note.append(node('p','',`${t('matched')}: ${sum.points} ${t('points')}. ${t('scopeNote')}`),node('p','',t('footer')));if(report.witnesses_truncated)note.append(node('p','',t('witnessWarning')));body.append(note,evidence(report));
  }
  body.append(provenance(report));
}
function render(){
  document.documentElement.lang=state.lang;document.title=state.lang==='ja'?'Segment Seam · GPX 境界の確認':'Segment Seam · GPX boundary review';
  document.querySelectorAll('[data-i18n]').forEach(element=>{element.textContent=t(element.dataset.i18n);});
  $('lang-en').setAttribute('aria-pressed',String(state.lang==='en'));$('lang-ja').setAttribute('aria-pressed',String(state.lang==='ja'));$('swap-button').setAttribute('aria-label',t('swap'));$('job-progress').setAttribute('aria-label',t('progress'));
  for(const side of ['before','after'])$(`${side}-file`).setAttribute('aria-label',t(`${side}File`));
  renderFiles();renderTracks();renderControls();renderReport();
}
async function setFile(side,file){
  const token=++fileTokens[side];invalidate(true);state.files[side]=null;state.errors[side]=fileProblem(file);state.loading[side]=!state.errors[side];render();
  if(state.errors[side])return;
  try {const data=bytesToBase64(new Uint8Array(await file.arrayBuffer()));if(token!==fileTokens[side])return;state.files[side]={name:file.name,size:file.size,data};state.errors[side]='';}
  catch {if(token===fileTokens[side])state.errors[side]='readFailed';}
  finally {if(token===fileTokens[side]){state.loading[side]=false;state.status=ready()?'ready':'initial';render();}}
}
function start(mode){
  if(state.busy||state.fatal||!ready()||(mode==='compare'&&!canCompare(state.inventory,state.beforeTrack,state.afterTrack,state.confirmed)))return;
  const payload={mode,before:{name:state.files.before.name,data:state.files.before.data},after:{name:state.files.after.name,data:state.files.after.data}};
  if(mode==='compare')Object.assign(payload,{before_track:Number(state.beforeTrack),after_track:Number(state.afterTrack),confirmed:true});
  invalidate(mode==='inspect');state.busy=true;state.mode=mode;state.status=mode==='inspect'?'inspecting':'comparing';render();runner.start(payload);
}
for(const side of ['before','after']) {
  $(`${side}-file`).addEventListener('change',event=>{const file=event.target.files[0];if(file)setFile(side,file);});
  const drop=$(`${side}-drop`);drop.addEventListener('dragover',event=>{event.preventDefault();drop.classList.add('dragging');});drop.addEventListener('dragleave',()=>drop.classList.remove('dragging'));drop.addEventListener('drop',event=>{event.preventDefault();drop.classList.remove('dragging');const file=event.dataTransfer.files[0];if(file){$(`${side}-file`).value='';setFile(side,file);}});
  $(`${side}-track`).addEventListener('change',event=>{const value=event.target.value;invalidate();state[`${side}Track`]=value;state.confirmed=false;render();});
}
$('same-track').addEventListener('change',event=>{const value=event.target.checked;invalidate();state.confirmed=value;render();});
$('inspect-button').addEventListener('click',()=>start('inspect'));$('compare-button').addEventListener('click',()=>start('compare'));
$('cancel-button').addEventListener('click',()=>{invalidate();state.status='cancelled';render();});
$('swap-button').addEventListener('click',()=>{if(!ready())return;invalidate(true);[state.files.before,state.files.after]=[state.files.after,state.files.before];state.errors.before=state.errors.after='';$('before-file').value=$('after-file').value='';render();});
$('restart-button').addEventListener('click',()=>{invalidate(true);fileTokens.before++;fileTokens.after++;state.files.before=state.files.after=null;state.loading.before=state.loading.after=false;state.errors.before=state.errors.after='';state.status='initial';state.mode=null;$('before-file').value=$('after-file').value='';render();});
for(const lang of ['en','ja'])$(`lang-${lang}`).addEventListener('click',()=>{state.lang=lang;render();});
$('demo-button').addEventListener('click',async()=>{
  invalidate(true);const own=revision;fileTokens.before++;fileTokens.after++;state.loading.before=state.loading.after=false;state.busy=true;state.mode='demo';state.status='demoLoading';demoAbort=new AbortController();const abort=demoAbort;render();
  try {const response=await fetch('api/demo',{signal:abort.signal,cache:'no-store'});if(!response.ok)throw new Error(`Demo failed (${response.status})`);const data=await response.json();if(own!==revision)return;
    for(const side of ['before','after']){if(typeof data[side]?.name!=='string'||typeof data[side]?.data!=='string')throw new Error(t('demoInvalid'));const bytes=atob(data[side].data);if(!bytes.length||bytes.length>MAX_FILE_BYTES)throw new Error(t('demoInvalid'));}
    for(const side of ['before','after']){state.files[side]={...data[side],size:atob(data[side].data).length,synthetic:true};state.errors[side]='';$(`${side}-file`).value='';}
    state.busy=false;state.status='ready';demoAbort=null;render();start('inspect');
  } catch(error){if(own!==revision||error.name==='AbortError')return;state.busy=false;state.status='failed';state.error=error.message;render();}
});
window.addEventListener('pagehide',()=>{runner.cancel().catch(()=>{});if(demoAbort)demoAbort.abort();});
render();
