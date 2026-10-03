# Local API contract

All URLs relative to random capability URL. `GET api/demo` returns `{before:{name,data},after:{name,data}}`, where data is base64.

`POST api/jobs` JSON: `{mode:"inspect"|"compare",before:{name,data},after:{name,data},before_track:1,after_track:1,confirmed:true}`. Compare requires explicit 1-based indices and `confirmed:true`; inspect ignores these. Maximum GPX bytes 4 MiB per file. Response 202 `{id}`; errors `{error}`.

`GET api/jobs/{id}` -> `{id,status:"running"|"done"|"error"|"cancelled",progress,result?,error?}`. `POST api/jobs/{id}/cancel` JSON `{}` returns same. Only one current job retained; inspect has no downloads. `GET api/jobs/{id}/packet.zip` available only for done compare. New jobs remove previous artifacts.

Inspect result: `{kind:"inventory",before:{name,sha256,bytes,tracks:[{index,name,points,segments,empty_segments}],waypoints,routes},after:{...},limits:{max_bytes:4194304,max_points:20000}}`.

Compare result is the entire report: `{kind:"comparison",schema:"segment-seam/1",status:"complete"|"unsupported",verdict:"boundaries_changed"|"boundaries_unchanged"|"not_compared",reasons:[string],scope:[string],before:{name,sha256,bytes,track:{index,name,points,segments,empty_segments}},after:{...},method:{name,radius_m,description},summary:{points,removed_boundaries,added_boundaries,retained_boundaries,before_distance_m,after_distance_m,artificial_distance_m,disconnected_distance_m,net_distance_change_m}|null,seams:[{left_point:2,right_point:3,change:"removed"|"added"|"retained",distance_m:123,before:{left_segment:1,right_segment:2},after:{left_segment:1,right_segment:1},left:{index,lat,lon,elevation:{state,text},time:{state,text}},right:{...}}],witnesses_truncated:false,metadata_note:string}`.

Point coordinates/elevation/time are strings, optional fields state absent or raw; do not present raw timestamps as elapsed time. Numeric measurements are spherical horizontal Haversine distances, not WGS84 ellipsoid or elevation-aware. No map/network GPS transmission. Seams are point adjacency boundaries; removed means a newly connected edge in the after segmentation. Status complete means only scoped boundary review, never full GPX equivalence or route safety. Unsupported report may still be downloaded for reasons but has no summary or seams. All file/name strings untrusted: render text only.
