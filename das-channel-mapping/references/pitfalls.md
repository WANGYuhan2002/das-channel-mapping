# Common pitfalls

Each of these happened at least once on a real cable.

**Conventions**
1. *Logged distance ≠ label.* A station list or hammer log quoting `D<n>` used the header distance, while the
   projects interpolated it as the nominal label: land positions slid back along the road by up to 159 m. Test
   the convention with the shots (conventions.md §2).
2. *Nominal spacing used for lengths.* 8 m instead of 8 × 1.0210 m: 2 % short on every fibre length (e.g. "48 m"
   of fibre that is really 49.6 m), wrong fibre/path ratios, wrong speeds.
3. *A coincidence hiding two errors.* A 2 % spacing error happened to cancel a 172 m coil at one shoreline, so
   an old map "matched" the shore; check both ends and the middle.
4. *Position = start of the gauge.* Positions must be gauge centres; tie every anchor that way.
5. *1 m CSV rounding.* `%.7g` on degrees keeps 5 decimals; write lat/lon with ≥ 7 decimals.

**Anchors**
6. *Trusting the first pick on a wide response.* Stack all blows; if the strong response is wide with the pick
   at one end and the neighbouring segments have −20 / +24 m of fibre, move the anchor to the equal-ratio
   channel inside the response (and record it).
7. *Two shots, one channel.* Merge them; two anchors 0.1 channel apart give a segment with nonsense ratios.
8. *Hammer strength read as coupling.* Blows on a manhole lid light up the coil inside. Use earthquakes.
9. *Background noise read as coupling.* On a quiet land cable it is instrument noise everywhere.
10. *Travel times used to place channels.* ~ms timing → ~10 m; use them as a check only.

**Paths**
11. *Straight lines between anchors.* 77 m p90 error on winding roads; use the road shape through the anchors.
12. *OSM centreline without the shift.* The shot points say which side of the road the cable is on: shift the
    road through both points.
13. *Automatic shoreline traces near the landing.* They were poor; the user's hand-drawn route was right. Ask
    for one where imagery is ambiguous, and then do not "improve" its shape with OSM.
14. *Wrong road at a junction.* A path much longer than the fibre (beyond the tolerance) means the shortest path
    took another road; use the reference route there.

**Slack**
15. *Spreading a coil.* One 155 m coil spread over a 180 m segment put its channels up to 56 m off.
16. *Every weak run is a coil.* A run can be fibre laid loosely along a detour (vehicles show it is not at one
    point). Check with vehicles before writing a block.
17. *Vehicles used for every channel.* Cars brake at corners; positions from "constant speed" are 10–30 m off at
    segment scale. Use vehicles for block points only.
18. *Block edges.* Half-channel edges make the block one channel too long when the end channels are half on the
    road; watch for fibre shorter than road next to a block (placement.md §3).

**Ends and checks**
19. *Assuming where the record ends.* "It ends at the node" forced the far end into an impossible fit; when
    nothing ties the end, say "not known" and place by the ratio along the full drawing.
20. *Checks against an old map.* An AIS offset or a residual computed before a rebuild is stale; rerun.
21. *Not telling users what moved.* Ship a per-channel change table and the list of products to redo.

**Process**
22. Never edit the original data, earlier result folders or someone else's tables: build new versions.
23. Visual picks (step windows, land / peak bands, which run is a coil, whether to write a block in) are the
    user's: show the figure, propose, wait.
24. Look at the raw waterfall and spectrum before calling something an artefact or a coil.
