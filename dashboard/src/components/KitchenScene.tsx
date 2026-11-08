import { useEffect, useRef, useState } from 'react'
import * as THREE from 'three'
import { OrbitControls } from 'three/addons/controls/OrbitControls.js'
import type { UploadPhase } from '@/hooks/useKitchenUpload'
import { advanceCooking, cookingDuration, initialCooking, smooth, type CookingStep } from '@/lib/cooking'

type Props = {
  stage: UploadPhase['kind']; batchId: number; paused: boolean; settled: boolean;
  onUpload: () => void; onServed: (batchId: number) => void; onStep: (step: CookingStep) => void;
}
export default function KitchenScene(props: Props) {
  const host = useRef<HTMLDivElement>(null)
  const live = useRef(props); live.current = props
  const [failed, setFailed] = useState(false)
  useEffect(() => {
    const el = host.current!
    let renderer: THREE.WebGLRenderer
    try { renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true }) }
    catch { setFailed(true); return }
    renderer.setPixelRatio(Math.min(devicePixelRatio, 2))
    renderer.shadowMap.enabled = true; renderer.shadowMap.type = THREE.PCFSoftShadowMap
    renderer.setClearColor('#eef3eb'); el.prepend(renderer.domElement)
    const scene = new THREE.Scene(); scene.fog = new THREE.Fog('#eef3eb', 22, 48)
    const camera = new THREE.PerspectiveCamera(34, 1, .1, 70)
    camera.position.set(9, 9, 13)
    const controls = new OrbitControls(camera, renderer.domElement)
    controls.target.set(-.25, .8, 0); controls.enableDamping = true; controls.enablePan = false; controls.enableZoom = false
    controls.minPolarAngle = .6; controls.maxPolarAngle = 1.05
    controls.minAzimuthAngle = .2; controls.maxAzimuthAngle = .85
    scene.add(new THREE.HemisphereLight('#ffffff', '#a2b09c', 3.1))
    const sun = new THREE.DirectionalLight('#fff1d7', 3.5); sun.position.set(-5, 10, 5); sun.castShadow = true
    sun.shadow.mapSize.set(2048, 2048); Object.assign(sun.shadow.camera, { left: -9, right: 9, top: 9, bottom: -9 }); sun.shadow.bias = -.0003; scene.add(sun)
    const accent = new THREE.PointLight('#7affee', 12, 14); accent.position.set(1, 4, -4); scene.add(accent)
    const material = (color: string, metalness = 0, roughness = .55) => new THREE.MeshStandardMaterial({ color, metalness, roughness })
    const metal = material('#7c9190', .8, .3), charcoal = material('#263532', .25, .4), porcelain = material('#fffff5', .12, .3)
    const cream = material('#f4dba6', 0, .45), cyan = new THREE.MeshBasicMaterial({ color: '#73e1cc' })
    const add = (geometry: THREE.BufferGeometry, mat: THREE.Material | THREE.Material[], parent: THREE.Object3D = scene, x = 0, y = 0, z = 0) => {
      const mesh = new THREE.Mesh(geometry, mat); mesh.position.set(x, y, z); mesh.castShadow = true; mesh.receiveShadow = true; parent.add(mesh); return mesh
    }
    const torus = (r: number, tube: number, mat: THREE.Material, parent: THREE.Object3D, x = 0, y = 0, z = 0) => {
      const mesh = add(new THREE.TorusGeometry(r, tube, 12, 96), mat, parent, x, y, z); mesh.rotation.x = Math.PI / 2; return mesh
    }
    add(new THREE.PlaneGeometry(100, 100), material('#eef3eb')).rotation.x = -Math.PI / 2
    // Quiet, rounded island. Most of the visual detail belongs to the food.
    const island = add(new THREE.CylinderGeometry(6.1, 6.1, .22, 96), porcelain, scene, 0, .2, 0); island.scale.z = .63
    const hob = add(new THREE.CylinderGeometry(2.12, 2.12, .055, 96), charcoal, scene, -1.25, .36, -.35)
    hob.receiveShadow = true
    const burner = torus(1.85, .019, cyan, scene, -1.25, .4, -.35)
    const pan = new THREE.Group(); pan.position.set(-1.25, .62, -.35); scene.add(pan)
    add(new THREE.CylinderGeometry(1.78, 1.64, .13, 96), metal, pan)
    add(new THREE.CylinderGeometry(1.69, 1.69, .025, 96), charcoal, pan, 0, .075, 0)
    torus(1.75, .05, metal, pan, 0, .11, 0)
    const handle = add(new THREE.BoxGeometry(2.55, .12, .28), metal, pan, -2.7, .03, 0); handle.rotation.z = .035
    add(new THREE.BoxGeometry(1.35, .18, .34), charcoal, pan, -3.1, .04, 0)
    add(new THREE.CylinderGeometry(1.48, 1.35, .1, 96), porcelain, scene, 2.65, .4, .45)
    torus(1.35, .032, material('#c4d0b9', .25), scene, 2.65, .47, .45)

    const canvas = document.createElement('canvas'); canvas.width = 512; canvas.height = 512
    const ctx = canvas.getContext('2d')!
    const gradient = ctx.createRadialGradient(256, 256, 15, 256, 256, 256)
    gradient.addColorStop(0, '#bf7b32'); gradient.addColorStop(.7, '#d69b4f'); gradient.addColorStop(1, '#efca83')
    ctx.fillStyle = gradient; ctx.fillRect(0, 0, 512, 512)
    let seed = 91; const random = () => { seed = seed * 16807 % 2147483647; return seed / 2147483647 }
    for (let i = 0; i < 14000; i++) { ctx.fillStyle = i % 3 ? 'rgba(105,53,12,.12)' : 'rgba(255,239,183,.4)'; ctx.beginPath(); ctx.arc(random() * 512, random() * 512, random() * 3 + .5, 0, Math.PI * 2); ctx.fill() }
    const texture = new THREE.CanvasTexture(canvas); texture.colorSpace = THREE.SRGBColorSpace
    const toasted = new THREE.MeshStandardMaterial({ map: texture, roughness: .88, transparent: true, opacity: 0, depthWrite: false })
    const batterTop = material('#f4dba6', 0, .37)
    const pancake = new THREE.Group(); scene.add(pancake)
    add(new THREE.CylinderGeometry(1.1, 1.12, .09, 96), [cream, batterTop, cream], pancake)
    const toastedSurface = add(new THREE.CircleGeometry(1.1, 96), toasted, pancake, 0, .046, 0); toastedSurface.rotation.x = -Math.PI / 2
    const butter = add(new THREE.BoxGeometry(.25, .055, .22), material('#ffe29b'), pancake, .1, .09, .05); butter.rotation.y = .3
    const syrup = add(new THREE.CylinderGeometry(.55, .55, .008, 48), new THREE.MeshPhysicalMaterial({ color: '#9e5a21', transparent: true, opacity: .58, roughness: .18 }), pancake, 0, .05, 0); syrup.scale.z = .8
    const bubbles: THREE.Mesh[] = []
    for (let i = 0; i < 28; i++) {
      const angle = random() * Math.PI * 2, r = Math.sqrt(random()) * .94
      const bubble = add(new THREE.SphereGeometry(.018 + random() * .035, 8, 6), material('#e1bc7a'), pancake, Math.cos(angle) * r, .045, Math.sin(angle) * r)
      bubble.scale.y = .5; bubbles.push(bubble)
    }
    // Open glass jug: visible batter surface, rounded lip, handle and actual spout.
    const jug = new THREE.Group(); scene.add(jug)
    const glass = new THREE.MeshPhysicalMaterial({ color: '#f4fff7', transparent: true, opacity: .28, roughness: .08, metalness: .05, side: THREE.DoubleSide, depthWrite: false })
    const profile = [new THREE.Vector2(.4, 0), new THREE.Vector2(.54, .05), new THREE.Vector2(.62, 1.15), new THREE.Vector2(.64, 1.25)]
    add(new THREE.LatheGeometry(profile, 64), glass, jug)
    add(new THREE.CylinderGeometry(.4, .4, .055, 48), glass, jug, 0, .02, 0)
    torus(.63, .025, material('#c1d1c5', .5, .2), jug, 0, 1.25, 0)
    const jugHandle = add(new THREE.TorusGeometry(.38, .065, 10, 48), glass, jug, -.7, .72, 0)
    jugHandle.scale.set(.8, 1.3, 1)
    const spout = add(new THREE.ConeGeometry(.22, .48, 4, 1, true), glass, jug, .67, 1.18, 0); spout.rotation.z = -Math.PI / 2
    const liquid = add(new THREE.CylinderGeometry(.57, .43, .9, 48), cream, jug, 0, .51, 0)
    const surface = add(new THREE.CircleGeometry(.57, 48), material('#ffe8b6', 0, .22), jug, 0, .965, 0); surface.rotation.x = -Math.PI / 2
    // The upload prompt is printed onto a curved glass label, so it belongs to the jug in 3D space.
    const labelCanvas = document.createElement('canvas'); labelCanvas.width = 768; labelCanvas.height = 192
    const labelCtx = labelCanvas.getContext('2d')!
    labelCtx.clearRect(0, 0, 512, 160)
    labelCtx.beginPath(); labelCtx.roundRect(16, 8, 736, 176, 30)
    labelCtx.fillStyle = 'rgba(255,255,242,.94)'; labelCtx.fill()
    labelCtx.strokeStyle = 'rgba(54,111,86,.82)'; labelCtx.lineWidth = 6; labelCtx.stroke()
    labelCtx.textAlign = 'center'; labelCtx.fillStyle = '#163f32'
    labelCtx.font = '700 54px monospace'; labelCtx.fillText('UPLOAD DATA', 384, 85)
    labelCtx.fillStyle = '#315d49'; labelCtx.font = '600 30px monospace'; labelCtx.fillText('CSV  ·  JSON', 384, 142)
    const labelTexture = new THREE.CanvasTexture(labelCanvas); labelTexture.colorSpace = THREE.SRGBColorSpace
    const labelMaterial = new THREE.MeshBasicMaterial({map:labelTexture,transparent:true,side:THREE.DoubleSide,depthWrite:false,polygonOffset:true,polygonOffsetFactor:-2,toneMapped:false})
    const visibleAngle = Math.atan2(2, 1.2)
    add(new THREE.CylinderGeometry(.632, .632, .5, 64, 1, true, visibleAngle - .85, 1.7), labelMaterial, jug, 0, .67, 0)
    const stream = add(new THREE.TubeGeometry(new THREE.LineCurve3(new THREE.Vector3(), new THREE.Vector3(0, -1, 0)), 24, .065, 8, false), cream)
    const spatula = new THREE.Group(); scene.add(spatula)
    add(new THREE.BoxGeometry(.72, .035, .85), metal, spatula)
    for (let i = 0; i < 3; i++) add(new THREE.BoxGeometry(.055, .008, .55), charcoal, spatula, (i - 1) * .16, .025, 0)
    add(new THREE.BoxGeometry(.13, .06, 1.7), metal, spatula, 0, 0, -1.15)
    add(new THREE.BoxGeometry(.2, .11, .8), charcoal, spatula, 0, 0, -1.8)
    const steam: THREE.Mesh[] = []
    for (let i = 0; i < 6; i++) {
      const curve = new THREE.CatmullRomCurve3([new THREE.Vector3(0, 0, 0), new THREE.Vector3(.08, .3, 0), new THREE.Vector3(-.08, .6, 0), new THREE.Vector3(.1, .9, 0)])
      steam.push(add(new THREE.TubeGeometry(curve, 16, .012, 4, false), new THREE.MeshBasicMaterial({ color: '#d7e7da', transparent: true, opacity: .3, depthWrite: false })))
    }
    const resize = () => { const w = el.clientWidth, h = el.clientHeight; if (!w || !h) return; renderer.setSize(w, h); camera.aspect = w / h; camera.fov = w / h < 1 ? 54 : 34; camera.updateProjectionMatrix() }
    const observer = new ResizeObserver(resize); observer.observe(el); resize()
    const media = matchMedia('(prefers-reduced-motion: reduce)')
    const jugRest = new THREE.Vector3(-3.35, .4, 2), jugPour = new THREE.Vector3(-2.7, 2.3, -.35)
    const panPosition = new THREE.Vector3(-1.25, .78, -.35), platePosition = new THREE.Vector3(2.65, .53, .45)
    const nozzle = new THREE.Vector3(), endpoint = new THREE.Vector3()
    const raycaster = new THREE.Raycaster(); const pointer = new THREE.Vector2(); let downX = 0, downY = 0
    const down = (event: PointerEvent) => { downX = event.clientX; downY = event.clientY }
    const up = (event: PointerEvent) => {
      if (Math.hypot(event.clientX - downX, event.clientY - downY) > 6 || (timeline.step !== 'ready' && timeline.step !== 'plated')) return
      const rect = renderer.domElement.getBoundingClientRect()
      raycaster.setFromCamera(new THREE.Vector2((event.clientX - rect.left) / rect.width * 2 - 1, -(event.clientY - rect.top) / rect.height * 2 + 1), camera)
      if ((timeline.step === 'ready' || timeline.step === 'plated') && raycaster.intersectObject(jug, true).length) live.current.onUpload()
    }
    const move = (event: PointerEvent) => {
      const rect=renderer.domElement.getBoundingClientRect(); pointer.set((event.clientX-rect.left)/rect.width*2-1,-(event.clientY-rect.top)/rect.height*2+1); raycaster.setFromCamera(pointer,camera)
      renderer.domElement.style.cursor=(timeline.step==='ready'||timeline.step==='plated')&&raycaster.intersectObject(jug,true).length?'pointer':'grab'
    }
    const key = (event: KeyboardEvent) => { if ((event.key==='Enter'||event.key===' ')&&(timeline.step==='ready'||timeline.step==='plated')) {event.preventDefault();live.current.onUpload()} }
    renderer.domElement.tabIndex=0; renderer.domElement.setAttribute('role','button'); renderer.domElement.setAttribute('aria-label','Batter jug. Activate to upload a CSV or JSON dataset.'); renderer.domElement.setAttribute('aria-keyshortcuts','Enter Space')
    renderer.domElement.addEventListener('pointerdown', down); renderer.domElement.addEventListener('pointerup', up); renderer.domElement.addEventListener('pointermove',move); renderer.domElement.addEventListener('keydown',key)
    let timeline = initialCooking(live.current.batchId, live.current.settled)
    let frame = 0, last = 0, notified = live.current.settled ? live.current.batchId : -1, lastStep: CookingStep | undefined
    const tick = (now: number) => {
      frame = requestAnimationFrame(tick)
      const delta = last ? Math.min((now - last) / 1000, .05) : 0; last = now
      timeline = advanceCooking(timeline, live.current.batchId, live.current.stage, delta, live.current.paused, media.matches)
      const { step, elapsed } = timeline
      if (lastStep !== step) { lastStep = step; live.current.onStep(step) }
      const pouring = step === 'pouring', cooking = step === 'cooking', flipping = step === 'flipping', plated = step === 'plated' || step === 'plating'
      const p = pouring ? Math.min(elapsed / cookingDuration.pouring, 1) : step === 'ready' ? 0 : 1
      const lift = pouring ? smooth(p / .3) * (1 - smooth((p - .78) / .22)) : 0
      jug.position.lerpVectors(jugRest, jugPour, lift); jug.rotation.z = -.95 * lift
      const spread = smooth((p - .28) / .5)
      const fullness = step === 'ready' ? 1 : 1 - spread * .48
      liquid.scale.y = fullness; liquid.position.y = .06 + .45 * fullness
      surface.position.y = .06 + .9 * fullness; surface.scale.setScalar(.85 + .15 * fullness)
      const f = flipping ? smooth(elapsed / cookingDuration.flipping) : plated ? 1 : 0
      pancake.visible = step !== 'ready' && (!pouring || p > .28)
      pancake.position.lerpVectors(panPosition, platePosition, f)
      if (flipping) pancake.position.y += Math.sin(f * Math.PI) * 2.7
      pancake.rotation.z = f * Math.PI * 2
      const scale = pouring ? .06 + spread * .94 : 1
      const settle = step === 'plating' && !media.matches ? Math.sin(elapsed * 20) * Math.exp(-elapsed * 8) * .045 : 0
      pancake.scale.set(scale * (1 + settle), 1 - settle, scale * (1 + settle))
      const brown = cooking ? smooth(elapsed / cookingDuration.cooking) : flipping || plated ? 1 : 0
      // Blend warm batter into a toasted surface without a material swap pop.
      batterTop.color.lerpColors(new THREE.Color('#f4dba6'), new THREE.Color('#c78c42'), brown)
      toasted.opacity = brown
      butter.visible = plated; syrup.visible = plated
      butter.scale.setScalar(step === 'plating' ? smooth(elapsed / .3) : 1)
      bubbles.forEach((bubble, i) => { bubble.visible = cooking && brown > i / bubbles.length * .7; const pulse = smooth((elapsed - i * .025) / .3); bubble.scale.y = pulse * .5 })
      stream.visible = pouring && p > .29 && p < .79 && !media.matches
      if (stream.visible) {
        jug.updateMatrixWorld(true); nozzle.set(.9, 1.18, 0).applyMatrix4(jug.matrixWorld)
        endpoint.copy(panPosition); endpoint.y += .04
        const mid = nozzle.clone().lerp(endpoint, .45); mid.x += .14
        const curve = new THREE.QuadraticBezierCurve3(nozzle, mid, endpoint)
        const old = stream.geometry; stream.geometry = new THREE.TubeGeometry(curve, 24, .065 * Math.sin(Math.PI * smooth((p - .29) / .5)) + .018, 8, false); old.dispose()
      }
      const spatulaLift = flipping ? Math.sin(f * Math.PI) : 0
      const slide = cooking ? smooth(elapsed / cookingDuration.cooking) : flipping ? 1 : 0
      if (flipping) spatula.position.set(THREE.MathUtils.lerp(-1.25, 2.65, f), .74 + spatulaLift * 1.5, THREE.MathUtils.lerp(-.35, .45, f))
      else if (step === 'plating') { const park = smooth(elapsed / cookingDuration.plating); spatula.position.set(THREE.MathUtils.lerp(2.65, 1.25, park), .6, THREE.MathUtils.lerp(.45, -1.65, park)) }
      else spatula.position.set(THREE.MathUtils.lerp(1.25, -1.25, slide), THREE.MathUtils.lerp(.6, .71, slide), THREE.MathUtils.lerp(-1.65, -.35, slide))
      spatula.rotation.set(flipping ? -.15 * Math.sin(f * Math.PI) : 0, -.15, flipping ? -.15 * Math.sin(f * Math.PI) : 0)
      steam.forEach((vapor, i) => { vapor.visible = cooking && elapsed > .3; const age = (elapsed * .35 + i / 6) % 1; vapor.position.set(-1.25 + Math.sin(i * 3) * .6 + age * .15, .9 + age * 1.2, -.35 + Math.cos(i * 4) * .6); (vapor.material as THREE.MeshBasicMaterial).opacity = Math.sin(age * Math.PI) * .3 })
      burner.scale.setScalar(cooking ? 1 + Math.sin(elapsed * 2) * .008 : 1)
      controls.update()
      renderer.render(scene, camera)
      if (step === 'plated' && live.current.stage === 'done' && notified !== timeline.batchId) { notified = timeline.batchId; live.current.onServed(timeline.batchId) }
    }
    frame = requestAnimationFrame(tick)
    const lost = (event: Event) => { event.preventDefault(); cancelAnimationFrame(frame); setFailed(true) }
    renderer.domElement.addEventListener('webglcontextlost', lost)
    return () => {
      cancelAnimationFrame(frame); observer.disconnect(); controls.dispose()
      renderer.domElement.removeEventListener('pointerdown', down); renderer.domElement.removeEventListener('pointerup', up); renderer.domElement.removeEventListener('pointermove',move); renderer.domElement.removeEventListener('keydown',key); renderer.domElement.removeEventListener('webglcontextlost', lost); labelTexture.dispose()
      // Includes materials temporarily replaced while cooking.
      const materials = new Set<THREE.Material>([batterTop, toasted, cream])
      scene.traverse(object => { if (object instanceof THREE.Mesh) { object.geometry.dispose(); (Array.isArray(object.material) ? object.material : [object.material]).forEach(mat => materials.add(mat)) } })
      materials.forEach(mat => mat.dispose()); texture.dispose(); sun.shadow.dispose(); renderer.dispose(); renderer.domElement.remove()
    }
  }, [])
  return <div className="station-render" ref={host} role="group" aria-label="3D kitchen with batter jug, skillet and serving plate">
    {failed && <div className="station-fallback"><div aria-hidden="true">🥞</div><h2>Your kitchen is ready.</h2><p>3D is unavailable on this device. Your upload and ranking still work.</p><button onClick={props.onUpload}>Upload dataset</button>{props.stage === 'done' && <button onClick={() => props.onServed(props.batchId)}>View results →</button>}</div>}
  </div>
}
