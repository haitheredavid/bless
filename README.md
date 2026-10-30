# bless

![bless: vibe shitty models, a hatched, badly triangulated cube in bauhaus poster style](docs/hero.svg)

Spin the models in 3D: **[haitheredavid.github.io/bless](https://haitheredavid.github.io/bless/)**

## what

I originally learned to model in rhino, but I never upgraded from rhino 7, and apparently they stopped supporting it on newer macOS with non-intel chips. So I moved over to Blender, because it works and it's free. But I really don't want to learn another modeling tool and all the stupid fucking buttons I'd need to dance around. In comes claudia and [blender-mcp](https://github.com/ahujasid/blender-mcp).

So, here's what this fucking thing does right now:

- **Vibe modeling, but parametric.** Models are built with Geometry Nodes driven by `Control` curves. You can grab those and drag them around by hand without the whole thing exploding. Usually.
- **Short sessions, long models.** Each model lives in `models/<name>/` and gets worked on over a bunch of short sittings. Every step is logged, so future me can figure out what the fuck past me was thinking.
- **Checkpoints.** Versions get published to [Speckle](https://speckle.systems), so there's a history that isn't just `model_final_FINAL_v3.blend`.
- **Lessons learned.** When a technique works, it gets written up in [`workflows/`](workflows/) so neither of us has to rediscover it next week.
- **Hand it to someone else.** A model can boil down to one panel of plain settings (size, box depth, letter weight) and a lit stage with cameras built into the `.blend`, so someone who's never opened Blender can drag sliders and hit F12. The printable parts quietly follow along. [`art-dealers-logo`](models/art-dealers-logo/brief.md) did this for my in-laws' gallery logo.

Agent context lives in [`AGENTS.md`](AGENTS.md) and [`.context/`](.context/). When something needs to exist in real life, its sibling [bambi](https://github.com/haitheredavid/bambi) takes over and prints it.

## how

### setup

macOS again. You'll need Blender, [uv](https://docs.astral.sh/uv/), [just](https://github.com/casey/just) and ffmpeg (for turntables):

```sh
brew install --cask blender
brew install uv just ffmpeg git-lfs
git lfs install
just setup
```

`just addon` installs or updates the MCP for Blender add-on (`uvx mcp-for-blender install-addon`). Restart Blender afterwards, because of course. The MCP server itself is wired up in `.mcp.json`.

### the agentic spice

In Claude Code:

- `/model <idea>`: plan a new model and create `models/<slug>/`
- `/session <model> [goal]`: one short sitting. It loads the brief, params and recent steps, models live in Blender, and logs each step
- `/checkpoint [msg]`: publish a Speckle version of whatever state it's in
- `/wrap`: promote steps into builders, then check, export and render. It also distills `workflows/`, checkpoints and offers a commit. Basically cleaning up after the party

bambi is enabled here as a Claude Code plugin. `just print-pack <model>` writes a print pack and `/bambi:print models/<model>` takes it from there. See [`workflows/print-handoff.md`](workflows/print-handoff.md).

### recipes

The `justfile` wraps the common commands:

```sh
just                       # list recipes
just new teapot            # new model + model.blend (metres; --unit mm for small parts), opened in Blender
just session teapot spout  # start a session note
just history teapot        # step timeline across sessions
just check teapot          # mesh health: loose geo, degenerate faces, flipped normals, transforms
just export teapot         # Model collection -> exports/*.glb (fbx/obj via [export] or --formats)
just render teapot         # studio render -> render.png + gallery below
just views teapot          # [[views]] shots -> out/views/
just turntable teapot      # 360° mp4 + gif in out/
just workflows             # workflow docs and the models that use them
```

## models

Every `just render` drops a fresh tile here. Click one for its brief; hover for what the hell it's supposed to be.

<!-- gallery:start -->
<p align="center">
<a href="models/art-dealers-logo/brief.md"><img src="docs/gallery/art-dealers-logo.png" width="24%" alt="art-dealers-logo" title="150 mm two-colour desk block of the Art Dealers Galeria logo, printed as one part on the P1S: an open black tray (3 mm floor, 4 mm rim, 15 mm tall) with the white logo standing inside up to the rim top; the &#x27;Dealers&#x27; letters are knocked out through the white box to the black floor."></a>
<a href="models/witch-frame/brief.md"><img src="docs/gallery/witch-frame.png" width="24%" alt="witch-frame" title="3D-printable shadow-box frame for a 9x12in witch illustration: concave bat-wing sides with flared corner tips, a face sloping from a thin outer edge into a deep sightwell, and a rabbet with snap-in flex prongs for the art stack."></a>
</p>
<!-- gallery:end -->
