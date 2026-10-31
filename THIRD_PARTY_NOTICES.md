# Third-party resource notes

This file documents the resources involved in the 2026-10-09 Ur-Ghast visual
revision. It is not a complete audit of all third-party resources in the pack.

## Twilight Forest

Original work: **The Twilight Forest**, by Benimatic / TeamTwilight.
Locked reference: Minecraft 1.20.1, Twilight Forest 4.3.2508.

- Repository: https://github.com/TeamTwilight/twilightforest
- Code license: LGPL-2.1-or-later,
  https://github.com/TeamTwilight/twilightforest/blob/1.20.x/LICENSE
- Non-code, non-sound assets: CC BY-NC-SA 4.0,
  https://github.com/TeamTwilight/twilightforest/blob/1.20.x/ASSET_LICENSE
- Sound assets are separately marked All Rights Reserved in the upstream README.

The three Ur-Ghast `towerboss` textures are adapted by changing their red hue to
yellow while retaining original lightness, saturation, pixel layout and alpha.
The ordinary texture is also used on the placed/worn trophy and its break
particles. Recolouring does not remove the original asset license conditions.
Input/output hashes and exact adaptation are recorded in
`tools/references/ur_ghast_review_20261009/source_lock.json`.

The historical source weather asset `textures/environment/bigrain.png` is not
the active Ur-Ghast rain renderer: this pack uses dimension-local native rain.
The falling tear particle is a separate boss-local effect.
No Ur-Ghast or Ghast Trap audio was copied in this visual revision; existing
sound bindings use native Minecraft/NetEase sound events.

## Minecraft ghast tear

The falling-tear sprite and `fiery_tears` inventory icon now use the unmodified
`assets/minecraft/textures/item/ghast_tear.png` from Mojang's official 1.20.1
client JAR. This is a Minecraft game resource, not an LGPL Twilight code asset.
Its origin and hashes are recorded in
`tools/references/minecraft_java_1_20_1/ghast_presentation/source_lock.json`.
The source JAR SHA-1 is `0c3ec587af28e5a785c0b4a7b8a30f9a8f78f838`.
