// Captured from the real engine against repository synthetic before/after fixtures.
const api=require('./api-fixtures.json');
const inventory=()=>{const value=structuredClone(api.inventory);for(const side of ['before','after'])value[side].tracks.push({...value[side].tracks[0],index:2,name:'Second synthetic track'});return value;};
const report=()=>structuredClone(api.report);
const unsupported=()=>structuredClone(api.unsupported);
module.exports={inventory,report,unsupported};
