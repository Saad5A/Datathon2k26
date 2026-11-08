import { useEffect, useRef } from 'react'
import * as THREE from 'three'
import { RoundedBoxGeometry } from 'three/addons/geometries/RoundedBoxGeometry.js'

export type StackCve = {
  id: string
  rank: number
  priority: string
  score: number
  title: string
  publicExploit: boolean
  vector: string
}

type Props = {
  stack: StackCve[]
  selectedId: string | null
  filterTier: 'ALL' | 'P0' | 'P1' | 'P2'
  onSelect: (cveId: string) => void
}

type PancakeUserData = {
  cve: StackCve
  restY: number
  restX: number
  dropDelay: number
  hasLanded: boolean
  isPancake: true
  selected: boolean
}

type Tendril = {
  root: THREE.Group
  tip: THREE.Mesh
  tipLocalX: number
  tipLocalY: number
  tipLocalZ: number
  speed: number
  hasFallingBead: boolean
}

type FallingBead = {
  mesh: THREE.Mesh
  tendril: Tendril
  vy: number
  age: number
  delay: number
}

type AnimPhase = 'LANDING' | 'POURING' | 'READY'

type DropActor = {
  object: THREE.Object3D
  restY: number
  startY: number
  restX: number
  startX: number
  delay: number
  fallDuration: number
  age: number
  phase: 'waiting' | 'falling' | 'done'
}

/** Soft organic landing: decelerate into rest. */
function easeOutCubic(t: number) {
  const u = 1 - t
  return 1 - u * u * u
}

function hashNoise(x: number, y: number, seed: number) {
  const n = Math.sin(x * 127.1 + y * 311.7 + seed * 74.7) * 43758.5453
  return n - Math.floor(n)
}

function fbm(angle: number, seed: number) {
  return (
    Math.sin(angle * 5 + seed) * 0.55 +
    Math.sin(angle * 11 + seed * 1.7) * 0.28 +
    Math.cos(angle * 17 - seed * 0.9) * 0.12 +
    (hashNoise(Math.cos(angle), Math.sin(angle), seed) - 0.5) * 0.18
  )
}

function seededRnd(seed: number) {
  let s = (Math.floor(seed * 16807) % 2147483647) + 1
  return () => {
    s = (s * 16807) % 2147483647
    return s / 2147483647
  }
}

/** Cooked batter map: caramelized center → pale fluffy rim + pore bump. */
function createBatterTextures(seed: number) {
  const size = 512
  const canvas = document.createElement('canvas')
  canvas.width = size
  canvas.height = size
  const ctx = canvas.getContext('2d')!
  const rnd = seededRnd(seed)
  const cx = size * 0.5
  const cy = size * 0.48

  const g = ctx.createRadialGradient(cx, cy, size * 0.06, cx, size * 0.5, size * 0.52)
  g.addColorStop(0, '#9E5B18')
  g.addColorStop(0.28, '#C47A2B')
  g.addColorStop(0.62, '#D49245')
  g.addColorStop(0.88, '#E8B878')
  g.addColorStop(1, '#F0C990')
  ctx.fillStyle = g
  ctx.fillRect(0, 0, size, size)

  for (let i = 0; i < 16000; i++) {
    const x = rnd() * size
    const y = rnd() * size
    const r = rnd() * 2.3 + 0.4
    ctx.fillStyle = i % 5 === 0 ? 'rgba(255,236,195,0.26)' : 'rgba(110,50,12,0.14)'
    ctx.beginPath()
    ctx.arc(x, y, r, 0, Math.PI * 2)
    ctx.fill()
  }
  for (let i = 0; i < 140; i++) {
    ctx.fillStyle = `rgba(70,28,6,${0.12 + rnd() * 0.14})`
    ctx.beginPath()
    ctx.ellipse(rnd() * size, rnd() * size, rnd() * 9 + 2, rnd() * 3 + 1, rnd() * Math.PI, 0, Math.PI * 2)
    ctx.fill()
  }

  const map = new THREE.CanvasTexture(canvas)
  map.colorSpace = THREE.SRGBColorSpace
  map.anisotropy = 4
  map.wrapS = map.wrapT = THREE.ClampToEdgeWrapping

  const bumpCanvas = document.createElement('canvas')
  bumpCanvas.width = 256
  bumpCanvas.height = 256
  const bctx = bumpCanvas.getContext('2d')!
  bctx.fillStyle = '#808080'
  bctx.fillRect(0, 0, 256, 256)
  for (let i = 0; i < 10000; i++) {
    const v = Math.floor(55 + rnd() * 90)
    bctx.fillStyle = `rgb(${v},${v},${v})`
    bctx.beginPath()
    bctx.arc(rnd() * 256, rnd() * 256, rnd() * 2.2 + 0.5, 0, Math.PI * 2)
    bctx.fill()
  }
  const bumpMap = new THREE.CanvasTexture(bumpCanvas)
  bumpMap.wrapS = bumpMap.wrapT = THREE.RepeatWrapping
  bumpMap.repeat.set(2.2, 2.2)
  return { map, bumpMap }
}

/**
 * Smooth syrup pool: dense cylinder disc with gentle convex dome + soft rim harmonics.
 * Avoids radial crease spikes from aggressive scallop pinching.
 */
function createOrganicSyrupCap(radius: number, thickness: number, seed: number) {
  const radial = 96
  const heightSegs = 8
  const geo = new THREE.CylinderGeometry(radius, radius, thickness, radial, heightSegs, false)
  const pos = geo.attributes.position
  const halfH = thickness * 0.5
  const dome = 0.055

  for (let i = 0; i < pos.count; i++) {
    let x = pos.getX(i)
    let y = pos.getY(i)
    let z = pos.getZ(i)
    const angle = Math.atan2(z, x)
    const r = Math.hypot(x, z)
    const edge = Math.min(1, r / (radius + 1e-6))
    // Low-frequency rim wobble only (no high-freq pinching → no specular spikes)
    const rimWave =
      1 +
      Math.sin(angle * 3 + seed) * 0.018 * edge * edge +
      Math.cos(angle * 5 - seed * 0.6) * 0.01 * edge * edge
    const newR = r * rimWave
    // Convex dome across the top so speculars glide smoothly
    const radialDome = (1 - edge * edge) * dome
    if (y > 0) {
      y = halfH * 0.35 + radialDome + edge * edge * (halfH * 0.15)
    } else {
      y = -halfH * 0.55 + edge * edge * 0.012
    }
    const scale = r > 1e-6 ? newR / r : 1
    pos.setXYZ(i, x * scale, y, z * scale)
  }
  pos.needsUpdate = true
  geo.computeVertexNormals()
  return geo
}

/** Wide meniscus → waist → teardrop tip. */
function createTaperedDrip(
  curve: THREE.CatmullRomCurve3,
  segs: number,
  radial: number,
  rStart: number,
  rMid: number,
  rEnd: number,
) {
  const positions: number[] = []
  const normals: number[] = []
  const indices: number[] = []
  const frames = curve.computeFrenetFrames(segs, false)

  for (let i = 0; i <= segs; i++) {
    const t = i / segs
    const p = curve.getPoint(t)
    const N = frames.normals[i]
    const B = frames.binormals[i]
    const envelope =
      t < 0.18
        ? THREE.MathUtils.lerp(rStart, rMid, t / 0.18)
        : t < 0.72
          ? THREE.MathUtils.lerp(rMid, rMid * 0.75, (t - 0.18) / 0.54)
          : THREE.MathUtils.lerp(rMid * 0.75, rEnd, (t - 0.72) / 0.28)
    for (let j = 0; j < radial; j++) {
      const a = (j / radial) * Math.PI * 2
      const cx = Math.cos(a)
      const sx = Math.sin(a)
      const nx = N.x * cx + B.x * sx
      const ny = N.y * cx + B.y * sx
      const nz = N.z * cx + B.z * sx
      positions.push(p.x + nx * envelope, p.y + ny * envelope, p.z + nz * envelope)
      normals.push(nx, ny, nz)
    }
  }
  for (let i = 0; i < segs; i++) {
    for (let j = 0; j < radial; j++) {
      const a = i * radial + j
      const b = i * radial + ((j + 1) % radial)
      const c = (i + 1) * radial + j
      const d = (i + 1) * radial + ((j + 1) % radial)
      indices.push(a, b, c, b, d, c)
    }
  }
  const geo = new THREE.BufferGeometry()
  geo.setAttribute('position', new THREE.Float32BufferAttribute(positions, 3))
  geo.setAttribute('normal', new THREE.Float32BufferAttribute(normals, 3))
  geo.setIndex(indices)
  geo.computeVertexNormals()
  return geo
}

function createDarkMapleMaterial() {
  // Maple syrup: translucent golden-amber, glossy. Attenuation darkens thick parts toward
  // medium brown while thin edges stay golden (base ~#9E5616 because ACES tone mapping lifts it toward #B8661B on screen; thick ~#8A4A12).
  return new THREE.MeshPhysicalMaterial({
    color: 0x9e5616,
    emissive: 0x3a1a05,
    emissiveIntensity: 0.12,
    roughness: 0.05,
    metalness: 0.02,
    clearcoat: 1.0,
    clearcoatRoughness: 0.04,
    transmission: 0.45,
    ior: 1.492,
    thickness: 0.6,
    transparent: true,
    opacity: 0.93,
    attenuationColor: new THREE.Color(0x8a4a12),
    attenuationDistance: 1.6,
  })
}

function createFluffyPancakeGeometry(baseRadius: number, height: number, seed: number, index: number) {
  const radial = 76
  const heightSegs = 9
  const radiusJitter = 1 + (hashNoise(index, seed, 3) - 0.5) * 0.08
  const radius = baseRadius * radiusJitter
  const geo = new THREE.CylinderGeometry(radius * 0.98, radius * 1.04, height, radial, heightSegs)
  const pos = geo.attributes.position

  for (let i = 0; i < pos.count; i++) {
    let x = pos.getX(i)
    let y = pos.getY(i)
    let z = pos.getZ(i)
    const angle = Math.atan2(z, x)
    const r = Math.hypot(x, z)
    const ny = y / (height * 0.5 + 1e-6)
    const edgeNoise = fbm(angle, seed + index)
    const muffin = Math.exp(-Math.pow((ny - 0.55) / 0.45, 2)) * 0.055
    const wallWobble = edgeNoise * 0.045 * (1 - Math.abs(ny) * 0.35)
    const lipRaise = Math.max(0, ny) * Math.max(0, (r / radius - 0.55) / 0.45) * 0.03
    const centerIndent = Math.max(0, 1 - r / (radius * 0.55)) * 0.024 * Math.max(0, ny)
    const scale = r > 1e-5 ? (r + wallWobble + muffin) / r : 1
    x *= scale
    z *= scale
    y = y + lipRaise - centerIndent + edgeNoise * 0.006 * ny
    pos.setXYZ(i, x, y, z)
  }
  geo.computeVertexNormals()
  return { geo, radius }
}

export function PancakeScene({ stack, selectedId, filterTier, onSelect }: Props) {
  const mountRef = useRef<HTMLDivElement>(null)
  const tooltipRef = useRef<HTMLDivElement>(null)
  const onSelectRef = useRef(onSelect)
  onSelectRef.current = onSelect

  const apiRef = useRef<{
    setSelected: (id: string | null) => void
    setFilter: (tier: 'ALL' | 'P0' | 'P1' | 'P2') => void
    rebuild: (next: StackCve[]) => void
  } | null>(null)

  useEffect(() => {
    const mount = mountRef.current
    const tooltip = tooltipRef.current
    if (!mount || !tooltip) return

    let disposed = false
    const prefersReducedMotion =
      typeof window !== 'undefined' && window.matchMedia('(prefers-reduced-motion: reduce)').matches

    const scene = new THREE.Scene()
    scene.background = new THREE.Color(0xfaf7f2)
    scene.fog = new THREE.FogExp2(0xfaf7f2, 0.035)

    const camera = new THREE.PerspectiveCamera(38, mount.clientWidth / Math.max(mount.clientHeight, 1), 0.1, 100)
    // Framed to show full stack + griddle plate (not clipped mid-stack)
    camera.position.set(0, 2.6, 6.2)
    camera.lookAt(0, -0.15, 0)

    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true })
    renderer.setSize(mount.clientWidth, mount.clientHeight)
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2))
    renderer.shadowMap.enabled = true
    renderer.shadowMap.type = THREE.PCFSoftShadowMap
    renderer.toneMapping = THREE.ACESFilmicToneMapping
    renderer.toneMappingExposure = 1.15
    mount.appendChild(renderer.domElement)

    const raycaster = new THREE.Raycaster()
    const mouse = new THREE.Vector2()
    const clock = new THREE.Clock()
    let targetRotationX = 0.35
    let targetRotationY = -0.45
    let hovered: THREE.Mesh | null = null

    let pancakeMeshes: THREE.Mesh[] = []
    let butterGroup: THREE.Group | null = null
    let syrupGroup: THREE.Group | null = null
    let pourStreamMesh: THREE.Mesh | null = null
    let syrupCapMesh: THREE.Mesh | null = null
    let syrupTendrilMeshes: Tendril[] = []
    let fallingBeads: FallingBead[] = []
    let dropActors: DropActor[] = []
    let animPhase: AnimPhase = prefersReducedMotion ? 'READY' : 'LANDING'
    let isLandingAnimationActive = !prefersReducedMotion
    let pourAge = 0
    let cameraShake = 0
    const camOrbitRadius = 6.2
    const camOrbitY = 2.6
    const camLookAt = new THREE.Vector3(0, -0.15, 0)
    const camBase = { x: 0, y: camOrbitY, z: camOrbitRadius }
    const textureCache: THREE.Texture[] = []
    const materialCache: THREE.Material[] = []

    const mapleMat = createDarkMapleMaterial()
    materialCache.push(mapleMat)

    // Warm culinary lighting
    scene.add(new THREE.AmbientLight(0xfff4e6, 0.85))
    scene.add(new THREE.HemisphereLight(0xfff8ee, 0xd4a574, 0.55))

    const keyLight = new THREE.DirectionalLight(0xfff5e6, 2.5)
    keyLight.position.set(4.2, 9.5, 5.2)
    keyLight.castShadow = true
    keyLight.shadow.mapSize.set(2048, 2048)
    keyLight.shadow.bias = -0.0005
    keyLight.shadow.normalBias = 0.02
    Object.assign(keyLight.shadow.camera, { left: -6, right: 6, top: 6, bottom: -6, near: 0.5, far: 28 })
    scene.add(keyLight)

    const rimLight = new THREE.DirectionalLight(0xff9e42, 3.0)
    rimLight.position.set(-5.5, 5.5, -4.5)
    scene.add(rimLight)

    const underFill = new THREE.PointLight(0xffc878, 1.2, 12)
    underFill.position.set(0.2, 0.35, 2.8)
    scene.add(underFill)

    const plate = new THREE.Mesh(
      new THREE.CylinderGeometry(2.85, 2.72, 0.16, 72),
      new THREE.MeshStandardMaterial({ color: 0xe8dfc8, roughness: 0.32, metalness: 0.08 }),
    )
    plate.position.y = -1.1
    plate.receiveShadow = true
    scene.add(plate)
    const plateRim = new THREE.Mesh(
      new THREE.TorusGeometry(2.86, 0.035, 16, 72),
      new THREE.MeshStandardMaterial({ color: 0x8b3a0f, roughness: 0.22, metalness: 0.55 }),
    )
    plateRim.rotation.x = Math.PI / 2
    plateRim.position.y = -1.015
    scene.add(plateRim)
    const contactShadow = new THREE.Mesh(
      new THREE.CircleGeometry(2.05, 64),
      new THREE.MeshBasicMaterial({ color: 0x3a2414, transparent: true, opacity: 0.18, depthWrite: false }),
    )
    contactShadow.rotation.x = -Math.PI / 2
    contactShadow.position.y = -1.018
    scene.add(contactShadow)

    function clearStack() {
      pancakeMeshes.forEach((m) => {
        scene.remove(m)
        m.geometry.dispose()
        const mats = Array.isArray(m.material) ? m.material : [m.material]
        mats.forEach((mat) => {
          if (mat && !materialCache.includes(mat as THREE.Material)) (mat as THREE.Material).dispose()
        })
      })
      pancakeMeshes = []

      if (butterGroup) {
        scene.remove(butterGroup)
        butterGroup.traverse((obj) => {
          if (obj instanceof THREE.Mesh) {
            obj.geometry.dispose()
            const mats = Array.isArray(obj.material) ? obj.material : [obj.material]
            mats.forEach((m) => {
              if (m && m !== mapleMat) (m as THREE.Material).dispose()
            })
          }
        })
        butterGroup = null
      }
      if (syrupGroup) {
        scene.remove(syrupGroup)
        syrupGroup.traverse((obj) => {
          if (obj instanceof THREE.Mesh) obj.geometry.dispose()
        })
        syrupGroup = null
      }
      pourStreamMesh = null
      syrupCapMesh = null
      syrupTendrilMeshes = []
      fallingBeads = []
      dropActors = []
      isLandingAnimationActive = !prefersReducedMotion
      pourAge = 0
      cameraShake = 0
      hovered = null
    }

    function snapToReady() {
      animPhase = 'READY'
      isLandingAnimationActive = false
      cameraShake = 0
      pancakeMeshes.forEach((p) => {
        const ud = p.userData as PancakeUserData
        p.position.set(ud.restX, ud.restY, 0)
        p.scale.set(1, 1, 1)
        p.visible = true
        ud.hasLanded = true
      })
      if (butterGroup) {
        butterGroup.position.set(butterGroup.userData.restX as number, butterGroup.userData.restY as number, 0.05)
        butterGroup.scale.set(1, 1, 1)
        butterGroup.visible = true
      }
      if (syrupGroup) {
        syrupGroup.visible = true
        syrupGroup.position.set((pancakeMeshes[0]?.userData as PancakeUserData | undefined)?.restX ?? 0, 0, 0)
        syrupGroup.scale.set(1, 1, 1)
      }
      if (syrupCapMesh) syrupCapMesh.scale.set(1, 1, 1)
      if (pourStreamMesh) {
        pourStreamMesh.visible = false
        pourStreamMesh.scale.set(0.001, 0.001, 0.001)
      }
      syrupTendrilMeshes.forEach((t) => {
        t.root.scale.set(1, 1, 1)
        t.tip.scale.set(1, 1.4, 1)
        t.tip.visible = true
        t.tip.position.set(t.tipLocalX, t.tipLocalY, t.tipLocalZ)
        const puddle = t.root.userData.puddle as THREE.Mesh | undefined
        if (puddle) {
          puddle.scale.set(1, 1, 1)
          puddle.visible = true
        }
      })
      fallingBeads.forEach((b, i) => {
        b.mesh.visible = !prefersReducedMotion
        b.age = -i * 0.55
        b.vy = 0
        resetFallingBead(b)
      })
    }

    function resetFallingBead(bead: FallingBead) {
      const t = bead.tendril
      bead.mesh.position.set(
        t.root.position.x + t.tipLocalX,
        t.root.position.y + t.tipLocalY * t.root.scale.y,
        t.root.position.z + t.tipLocalZ,
      )
      bead.vy = 0
      bead.mesh.scale.set(0.75, 1.35, 0.75)
    }

    /** After pancakes seat — pour stream → pool → front drips (no syrup hard-land). */
    function beginPour() {
      animPhase = 'POURING'
      pourAge = 0
      // Keep interactions locked until pour finishes
      isLandingAnimationActive = true
      const topX = (pancakeMeshes[0]?.userData as PancakeUserData | undefined)?.restX ?? 0

      if (syrupGroup) {
        syrupGroup.visible = true
        syrupGroup.position.set(topX, 0, 0)
        syrupGroup.scale.set(1, 1, 1)
      }
      if (syrupCapMesh) syrupCapMesh.scale.set(0.08, 0.35, 0.08)
      if (pourStreamMesh) {
        pourStreamMesh.visible = true
        pourStreamMesh.scale.set(1, 0.05, 1)
      }
      syrupTendrilMeshes.forEach((t) => {
        t.root.scale.set(1, 0.001, 1)
        t.tip.scale.set(0.001, 0.001, 0.001)
        t.tip.visible = false
        t.tip.position.set(t.tipLocalX, t.tipLocalY, t.tipLocalZ)
        const puddle = t.root.userData.puddle as THREE.Mesh | undefined
        if (puddle) {
          puddle.scale.set(0.01, 1, 0.01)
          puddle.visible = false
        }
      })
      fallingBeads.forEach((b) => {
        b.mesh.visible = false
        b.vy = 0
        b.age = -b.delay
        resetFallingBead(b)
      })
      if (butterGroup) {
        butterGroup.visible = true
        butterGroup.position.set(butterGroup.userData.restX as number, butterGroup.userData.restY as number, 0.05)
        butterGroup.scale.set(0.01, 0.01, 0.01)
      }
    }

    function buildPancakeStack(items: StackCve[]) {
      clearStack()
      if (!items.length) return

      const num = items.length
      const height = 0.28
      // Seat bottom pancake on plate top (~-1.02): center ≈ plateTop + halfHeight
      let targetY = -0.85
      const built: THREE.Mesh[] = new Array(num)

      for (let i = num - 1; i >= 0; i--) {
        const seed = (items[i].id.charCodeAt(items[i].id.length - 1) || 7) + i * 13
        const baseRadius = 1.7 - i * 0.048
        const { geo } = createFluffyPancakeGeometry(baseRadius, height, seed, i)
        const { map, bumpMap } = createBatterTextures(seed + i * 17)
        textureCache.push(map, bumpMap)

        const mat = new THREE.MeshStandardMaterial({
          map,
          bumpMap,
          bumpScale: 0.042,
          roughness: 0.84 + hashNoise(i, 2, seed) * 0.04,
          metalness: 0.04,
          transparent: true,
          opacity: 1,
          envMapIntensity: 0.32,
        })
        materialCache.push(mat)

        const mesh = new THREE.Mesh(geo, mat)
        mesh.castShadow = true
        mesh.receiveShadow = true

        const gap = 0.02 + hashNoise(i, seed, 1) * 0.035
        // Top (P0) rests a little to the right of stack center
        const restX = i === 0 ? 0.16 : Math.sin(i * 1.1) * 0.05
        const tiltAmp = THREE.MathUtils.degToRad(1.5 + hashNoise(i, 4, seed) * 1.0)

        // Stage above camera; invisible until drop begins
        const fromBottom = num - 1 - i
        const startY = 11 + fromBottom * 1.2 + hashNoise(i, seed, 5) * 0.9
        mesh.position.set(restX, prefersReducedMotion ? targetY : startY, 0)
        mesh.visible = prefersReducedMotion
        mesh.scale.set(1, 1, 1)
        mesh.rotation.y = i * 0.55 + hashNoise(i, 1, seed) * 0.4
        mesh.rotation.x = Math.sin(i * 1.7 + seed) * tiltAmp
        mesh.rotation.z = Math.cos(i * 1.3 - seed) * tiltAmp - 0.015

        mesh.userData = {
          cve: items[i],
          restY: targetY,
          restX,
          // Slowed stagger: bottom first, top last
          dropDelay: 0.25 + fromBottom * 0.38,
          hasLanded: prefersReducedMotion,
          isPancake: true,
          selected: false,
        } satisfies PancakeUserData
        mesh.userData.startY = startY
        // Top pancake falls straight down onto its rightward rest — no lateral drift
        mesh.userData.startX = i === 0 ? restX : restX - 0.1

        scene.add(mesh)
        built[i] = mesh
        targetY += height * 0.98 + gap
      }
      pancakeMeshes = built

      const top = built[0]
      const topUd = top.userData as PancakeUserData
      const topY = topUd.restY + 0.16

      // --- Syrup hierarchy (hidden until pour after pancakes seat) ---
      syrupGroup = new THREE.Group()
      syrupGroup.position.set(topUd.restX, 0, 0)
      syrupGroup.visible = prefersReducedMotion
      scene.add(syrupGroup)

      // Pour stream aimed at butter
      const streamGeo = new THREE.CylinderGeometry(0.045, 0.07, 5.5, 14)
      streamGeo.translate(0, 2.75, 0)
      pourStreamMesh = new THREE.Mesh(streamGeo, mapleMat)
      pourStreamMesh.position.set(0.1, topY + 0.2, 0.05)
      pourStreamMesh.scale.set(0.001, 0.001, 0.001)
      pourStreamMesh.castShadow = true
      pourStreamMesh.visible = false
      syrupGroup.add(pourStreamMesh)

      // Organic crown — scales out during pour
      const capRadius = 1.4
      syrupCapMesh = new THREE.Mesh(createOrganicSyrupCap(capRadius, 0.09, 2.4), mapleMat)
      syrupCapMesh.position.set(0, topY, 0)
      syrupCapMesh.scale.set(prefersReducedMotion ? 1 : 0.08, prefersReducedMotion ? 1 : 0.35, prefersReducedMotion ? 1 : 0.08)
      syrupCapMesh.castShadow = true
      syrupCapMesh.receiveShadow = true
      syrupGroup.add(syrupCapMesh)

      // Contoured clinging streams — reach plate surface so bulbs + puddles finish seated
      const topCapY = topY
      const plateSurfaceY = -1.0
      const contouredDrips = [
        // Right front-facing main drool
        {
          points: [
            new THREE.Vector3(1.22, topCapY + 0.02, 0.45),
            new THREE.Vector3(1.34, topCapY - 0.25, 0.48),
            new THREE.Vector3(1.3, topCapY - 0.65, 0.46),
            new THREE.Vector3(1.26, (topCapY + plateSurfaceY) * 0.45, 0.44),
            new THREE.Vector3(1.24, plateSurfaceY + 0.02, 0.42),
          ],
          r0: 0.065,
          r1: 0.035,
          r2: 0.055,
          speed: 1.35,
          front: true,
          fall: true,
          hasPuddle: true,
          puddleRadius: 0.16,
        },
        // Right flank secondary drip
        {
          points: [
            new THREE.Vector3(1.1, topCapY + 0.02, 0.72),
            new THREE.Vector3(1.24, topCapY - 0.3, 0.75),
            new THREE.Vector3(1.2, topCapY - 0.55, 0.72),
            new THREE.Vector3(1.18, plateSurfaceY + 0.12, 0.7),
          ],
          r0: 0.055,
          r1: 0.03,
          r2: 0.048,
          speed: 1.15,
          front: true,
          fall: false,
          hasPuddle: false,
          puddleRadius: 0.12,
        },
        // Right back clinging drip
        {
          points: [
            new THREE.Vector3(1.28, topCapY + 0.02, 0.15),
            new THREE.Vector3(1.38, topCapY - 0.35, 0.18),
            new THREE.Vector3(1.34, topCapY - 0.7, 0.17),
            new THREE.Vector3(1.33, (topCapY + plateSurfaceY) * 0.42, 0.16),
            new THREE.Vector3(1.32, plateSurfaceY + 0.02, 0.16),
          ],
          r0: 0.058,
          r1: 0.032,
          r2: 0.05,
          speed: 1.22,
          front: false,
          fall: true,
          hasPuddle: true,
          puddleRadius: 0.12,
        },
        // Front-center drool toward camera
        {
          points: [
            new THREE.Vector3(0.12, topCapY + 0.02, 1.18),
            new THREE.Vector3(0.14, topCapY - 0.28, 1.32),
            new THREE.Vector3(0.13, topCapY - 0.7, 1.28),
            new THREE.Vector3(0.12, (topCapY + plateSurfaceY) * 0.4, 1.22),
            new THREE.Vector3(0.12, plateSurfaceY + 0.02, 1.2),
          ],
          r0: 0.072,
          r1: 0.036,
          r2: 0.06,
          speed: 1.4,
          front: true,
          fall: true,
          hasPuddle: true,
          puddleRadius: 0.18,
        },
        // Front-left creep
        {
          points: [
            new THREE.Vector3(-0.55, topCapY + 0.02, 1.12),
            new THREE.Vector3(-0.62, topCapY - 0.32, 1.26),
            new THREE.Vector3(-0.58, topCapY - 0.72, 1.2),
            new THREE.Vector3(-0.54, plateSurfaceY + 0.14, 1.1),
          ],
          r0: 0.06,
          r1: 0.03,
          r2: 0.048,
          speed: 1.12,
          front: true,
          fall: false,
          hasPuddle: false,
          puddleRadius: 0.12,
        },
      ]

      fallingBeads = []
      contouredDrips.forEach((cfg, idx) => {
        const anchor = cfg.points[0]
        const tipWorld = cfg.points[cfg.points.length - 1]
        // Local curve relative to meniscus anchor so growth scales along the strand
        const localPts = cfg.points.map((p) => new THREE.Vector3(p.x - anchor.x, p.y - anchor.y, p.z - anchor.z))
        const curve = new THREE.CatmullRomCurve3(localPts)
        const tipLocal = localPts[localPts.length - 1]

        const root = new THREE.Group()
        root.position.copy(anchor)
        root.userData.front = cfg.front
        root.userData.dripSpeed = cfg.speed
        root.userData.dripDelay = cfg.front ? 0.32 + idx * 0.07 : 0.48 + idx * 0.06
        root.scale.set(1, prefersReducedMotion ? 1 : 0.001, 1)

        const drip = new THREE.Mesh(createTaperedDrip(curve, 48, 12, cfg.r0, cfg.r1, cfg.r2), mapleMat)
        drip.castShadow = true
        root.add(drip)

        // Bulbous teardrop tip
        const tip = new THREE.Mesh(new THREE.SphereGeometry(cfg.r2 * 1.45, 18, 18), mapleMat)
        tip.position.copy(tipLocal)
        tip.scale.set(
          prefersReducedMotion ? 1 : 0.001,
          prefersReducedMotion ? 1.4 : 0.001,
          prefersReducedMotion ? 1 : 0.001,
        )
        tip.castShadow = true
        tip.visible = prefersReducedMotion
        root.add(tip)

        syrupGroup!.add(root)
        const tendril: Tendril = {
          root,
          tip,
          tipLocalX: tipLocal.x,
          tipLocalY: tipLocal.y,
          tipLocalZ: tipLocal.z,
          speed: cfg.speed,
          hasFallingBead: cfg.fall,
        }
        syrupTendrilMeshes.push(tendril)

        // Settled puddle on the griddle under the strand tip
        if (cfg.hasPuddle) {
          const puddle = new THREE.Mesh(
            new THREE.CylinderGeometry(cfg.puddleRadius, cfg.puddleRadius * 1.05, 0.015, 24),
            mapleMat,
          )
          puddle.position.set(tipWorld.x, plateSurfaceY + 0.005, tipWorld.z)
          puddle.receiveShadow = true
          puddle.scale.set(prefersReducedMotion ? 1 : 0.01, 1, prefersReducedMotion ? 1 : 0.01)
          puddle.userData.isPuddle = true
          puddle.userData.dripDelay = (root.userData.dripDelay as number) + 0.55
          syrupGroup!.add(puddle)
          root.userData.puddle = puddle
        }

        if (cfg.fall && !prefersReducedMotion) {
          const bead = new THREE.Mesh(new THREE.SphereGeometry(cfg.r2 * 1.1, 14, 14), mapleMat)
          bead.castShadow = true
          bead.visible = false
          bead.scale.set(0.75, 1.35, 0.75)
          syrupGroup!.add(bead)
          fallingBeads.push({
            mesh: bead,
            tendril,
            vy: 0,
            age: -idx * 0.45,
            delay: 0.35 + idx * 0.4,
          })
        }
      })

      // Softened butter + melt ring
      butterGroup = new THREE.Group()
      const melt = new THREE.Mesh(
        new THREE.CircleGeometry(0.38, 32),
        new THREE.MeshPhysicalMaterial({
          color: 0xffd84d,
          roughness: 0.08,
          metalness: 0.02,
          transmission: 0.55,
          ior: 1.38,
          thickness: 0.35,
          clearcoat: 1,
          clearcoatRoughness: 0.08,
          transparent: true,
          opacity: 0.92,
        }),
      )
      melt.rotation.x = -Math.PI / 2
      melt.position.set(0, -0.1, 0)
      butterGroup.add(melt)

      const butter = new THREE.Mesh(
        new RoundedBoxGeometry(0.46, 0.22, 0.42, 4, 0.08),
        new THREE.MeshPhysicalMaterial({
          color: 0xffe066,
          roughness: 0.22,
          metalness: 0.02,
          clearcoat: 0.7,
          clearcoatRoughness: 0.15,
          transmission: 0.28,
          ior: 1.4,
          thickness: 0.4,
        }),
      )
      butter.rotation.set(0.12, 0.55, 0.08)
      butter.castShadow = true
      butterGroup.add(butter)

      const butterRestY = topY + 0.12
      const butterRestX = topUd.restX + 0.1
      butterGroup.position.set(butterRestX, butterRestY, 0.05)
      butterGroup.userData = { restY: butterRestY, restX: butterRestX }
      butterGroup.visible = prefersReducedMotion
      butterGroup.scale.set(prefersReducedMotion ? 1 : 0.01, prefersReducedMotion ? 1 : 0.01, prefersReducedMotion ? 1 : 0.01)
      scene.add(butterGroup)

      if (!prefersReducedMotion) {
        syrupGroup.visible = false
        syrupTendrilMeshes.forEach((t) => {
          t.root.scale.set(1, 0.001, 1)
          t.tip.visible = false
        })
      }

      dropActors = []
      if (!prefersReducedMotion) {
        isLandingAnimationActive = true
        animPhase = 'LANDING'
        // Pancakes only — smooth settle, no bounce; syrup pours after
        pancakeMeshes.forEach((mesh, i) => {
          const ud = mesh.userData as PancakeUserData
          dropActors.push({
            object: mesh,
            restY: ud.restY,
            startY: mesh.userData.startY as number,
            restX: ud.restX,
            startX: (mesh.userData.startX as number) ?? ud.restX,
            delay: ud.dropDelay,
            fallDuration: i === 0 ? 1.05 : 0.95,
            age: 0,
            phase: 'waiting',
          })
        })
        clock.start()
      } else {
        snapToReady()
      }
    }

    function updateDropActor(actor: DropActor, dt: number) {
      actor.age += dt
      if (actor.phase === 'waiting') {
        if (actor.age < actor.delay) return
        actor.phase = 'falling'
        actor.object.visible = true
      }

      if (actor.phase === 'falling') {
        const t = Math.min(1, (actor.age - actor.delay) / actor.fallDuration)
        const ease = easeOutCubic(t)
        actor.object.position.y = THREE.MathUtils.lerp(actor.startY, actor.restY, ease)
        actor.object.position.x = THREE.MathUtils.lerp(actor.startX, actor.restX, ease)
        actor.object.scale.set(1, 1, 1)
        if (t >= 1) {
          actor.object.position.y = actor.restY
          actor.object.position.x = actor.restX
          actor.phase = 'done'
          if (actor.object instanceof THREE.Mesh) {
            ;(actor.object.userData as PancakeUserData).hasLanded = true
          }
        }
      }
    }

    function updatePhysicsAndAnimations(dt: number) {
      if (cameraShake > 0) cameraShake = Math.max(0, cameraShake - dt * 0.55)

      if (animPhase === 'LANDING') {
        dropActors.forEach((a) => updateDropActor(a, dt))
        if (dropActors.length > 0 && dropActors.every((a) => a.phase === 'done')) {
          pancakeMeshes.forEach((m) => {
            const ud = m.userData as PancakeUserData
            m.position.set(ud.restX, ud.restY, 0)
            m.scale.set(1, 1, 1)
            m.visible = true
          })
          beginPour()
        }
      } else if (animPhase === 'POURING') {
        pourAge += dt
        // Long enough for slowest drip + puddle expand to finish before READY snap
        const pourDuration = 3.05
        const t = Math.min(1, pourAge / pourDuration)

        // Stream pours down, then pinches off
        if (pourStreamMesh) {
          const streamT = Math.min(1, pourAge / 0.55)
          pourStreamMesh.scale.set(1, 0.05 + streamT * 0.95, 1)
          if (pourAge > 1.5) {
            const pinch = Math.min(1, (pourAge - 1.5) / 0.7)
            const r = Math.max(0.001, 1 - easeOutCubic(pinch))
            pourStreamMesh.scale.x = r
            pourStreamMesh.scale.z = r
            if (pinch >= 1) pourStreamMesh.visible = false
          }
        }

        // Cap spreads like poured syrup
        if (syrupCapMesh) {
          const capT = easeOutCubic(Math.min(1, Math.max(0, (pourAge - 0.2) / 1.0)))
          const s = 0.08 + capT * 0.92
          syrupCapMesh.scale.set(s, 0.35 + capT * 0.65, s)
        }

        // Contoured drips grow along strand; tip beads + plate puddles settle after
        syrupTendrilMeshes.forEach((tendril) => {
          const delay = (tendril.root.userData.dripDelay as number) ?? 0.45
          const speed = tendril.speed
          const local = Math.min(1, Math.max(0, (pourAge - delay) / (1.15 / speed)))
          const e = easeOutCubic(local)
          tendril.root.scale.set(1, Math.max(0.001, e), 1)
          tendril.tip.visible = local > 0.55
          const tipS = Math.max(0.001, THREE.MathUtils.lerp(0.35, 1, Math.max(0, (local - 0.55) / 0.45)))
          tendril.tip.scale.set(tipS, tipS * 1.4, tipS)

          const puddle = tendril.root.userData.puddle as THREE.Mesh | undefined
          if (puddle) {
            const pDelay = (puddle.userData.dripDelay as number) ?? delay + 0.55
            const pT = easeOutCubic(Math.min(1, Math.max(0, (pourAge - pDelay) / 0.55)))
            const ps = Math.max(0.01, pT)
            puddle.scale.set(ps, 1, ps)
            puddle.visible = pT > 0.02
          }
        })

        // Butter emerges once syrup has pooled
        if (butterGroup) {
          const bT = easeOutCubic(Math.min(1, Math.max(0, (pourAge - 0.5) / 0.55)))
          const s = 0.01 + bT * 0.99
          butterGroup.scale.set(s, s, s)
          butterGroup.visible = bT > 0.02
        }

        if (t >= 1) {
          // Force finished resting state — streams, bulbs, puddles fully expanded
          animPhase = 'READY'
          isLandingAnimationActive = false
          if (pourStreamMesh) {
            pourStreamMesh.visible = false
            pourStreamMesh.scale.set(0.001, 0.001, 0.001)
          }
          if (syrupCapMesh) syrupCapMesh.scale.set(1, 1, 1)
          if (butterGroup) butterGroup.scale.set(1, 1, 1)
          syrupTendrilMeshes.forEach((tendril) => {
            tendril.root.scale.set(1, 1, 1)
            tendril.tip.visible = true
            tendril.tip.scale.set(1, 1.4, 1)
            tendril.tip.position.set(tendril.tipLocalX, tendril.tipLocalY, tendril.tipLocalZ)
            const puddle = tendril.root.userData.puddle as THREE.Mesh | undefined
            if (puddle) {
              puddle.scale.set(1, 1, 1)
              puddle.visible = true
            }
          })
          fallingBeads.forEach((b, i) => {
            b.mesh.visible = true
            b.age = -i * 0.55
            b.vy = 0
            resetFallingBead(b)
          })
        }
      }

      if (animPhase === 'READY') {
        const time = clock.elapsedTime
        pancakeMeshes.forEach((mesh) => {
          const ud = mesh.userData as PancakeUserData
          const lift = hovered === mesh ? 0.08 : 0
          const slide = ud.selected ? 0.38 : 0
          mesh.position.y += (ud.restY + lift - mesh.position.y) * 0.14
          mesh.position.x += (ud.restX + slide - mesh.position.x) * 0.14
        })

        const top = pancakeMeshes[0]
        if (top) {
          const ud = top.userData as PancakeUserData
          const dx = top.position.x - ud.restX
          const dy = top.position.y - ud.restY
          if (butterGroup) {
            butterGroup.position.x = (butterGroup.userData.restX as number) + dx
            butterGroup.position.y = (butterGroup.userData.restY as number) + dy
          }
          if (syrupGroup) {
            syrupGroup.position.x = ud.restX + dx
            syrupGroup.position.y = dy
          }

          // Peristaltic tip breathing — stretch / pinch before drip-off
          syrupTendrilMeshes.forEach((t, idx) => {
            const dripPulse = Math.sin(time * 2.0 + idx * 1.15) * 0.015
            t.tip.position.set(t.tipLocalX, t.tipLocalY - dripPulse, t.tipLocalZ)
            t.tip.scale.set(1 + dripPulse * 2, 1.4 - dripPulse * 2, 1 + dripPulse * 2)
          })

          // Continuous falling beads: stretch off tip → gravity → plate → loop
          const plateYLocal = -1.0 - dy
          fallingBeads.forEach((bead) => {
            bead.age += dt
            if (bead.age < 0) {
              resetFallingBead(bead)
              bead.mesh.visible = false
              return
            }
            bead.mesh.visible = true
            bead.vy -= 9.2 * dt
            bead.mesh.position.y += bead.vy * dt
            // Keep XZ locked under the hanging tip
            const t = bead.tendril
            bead.mesh.position.x = t.root.position.x + t.tipLocalX
            bead.mesh.position.z = t.root.position.z + t.tipLocalZ
            bead.mesh.scale.set(0.75, 1.35, 0.75)

            if (bead.mesh.position.y <= plateYLocal) {
              bead.age = -0.35 - Math.random() * 0.55
              bead.vy = 0
              resetFallingBead(bead)
              bead.mesh.visible = false
            }
          })
        }
      }
    }

    function setMaterialOpacity(root: THREE.Object3D, opacity: number, transparent: boolean) {
      root.traverse((obj) => {
        if (obj instanceof THREE.Mesh && obj.material) {
          const mats = Array.isArray(obj.material) ? obj.material : [obj.material]
          mats.forEach((m) => {
            const mat = m as THREE.MeshStandardMaterial
            if ('opacity' in mat) {
              mat.transparent = transparent || opacity < 1
              mat.opacity = opacity
              mat.needsUpdate = true
            }
          })
        }
      })
    }

    function applyFilter(tier: 'ALL' | 'P0' | 'P1' | 'P2') {
      pancakeMeshes.forEach((mesh) => {
        const cve = (mesh.userData as PancakeUserData).cve
        const match = tier === 'ALL' || cve.priority === tier
        setMaterialOpacity(mesh, match ? 1 : 0.22, !match)
      })
      const syrupOpacity = tier === 'ALL' || tier === 'P0' ? 1 : 0.35
      if (syrupGroup) setMaterialOpacity(syrupGroup, syrupOpacity, true)
      if (butterGroup) setMaterialOpacity(butterGroup, syrupOpacity, true)
    }

    function setSelected(id: string | null) {
      pancakeMeshes.forEach((mesh) => {
        ;(mesh.userData as PancakeUserData).selected = (mesh.userData as PancakeUserData).cve.id === id
      })
    }

    buildPancakeStack(stack)
    applyFilter(filterTier)
    setSelected(selectedId)

    apiRef.current = {
      setSelected,
      setFilter: applyFilter,
      rebuild: (next) => {
        buildPancakeStack(next)
        applyFilter(filterTier)
        setSelected(selectedId)
      },
    }

    const tipId = tooltip.querySelector('[data-tip-id]') as HTMLElement
    const tipPri = tooltip.querySelector('[data-tip-pri]') as HTMLElement
    const tipName = tooltip.querySelector('[data-tip-name]') as HTMLElement

    function showTooltip(mesh: THREE.Mesh, x: number, y: number) {
      if (!tooltip || !mount || !tipId || !tipName || !tipPri) return
      const cve = (mesh.userData as PancakeUserData).cve
      tipId.textContent = cve.id
      tipName.textContent = cve.title
      tipPri.textContent = cve.priority
      tipPri.className =
        'px-1.5 py-0.5 rounded text-[10px] font-mono ' +
        (cve.priority === 'P0'
          ? 'bg-red-500/20 text-red-300'
          : cve.priority === 'P1'
            ? 'bg-amber-500/20 text-amber-300'
            : 'bg-gray-500/20 text-gray-300')
      tooltip.style.left = `${Math.min(x + 15, mount.clientWidth - 270)}px`
      tooltip.style.top = `${Math.max(y - 30, 20)}px`
      tooltip.style.opacity = '1'
    }

    function onMouseMove(event: MouseEvent) {
      if (!mount || !tooltip) return
      const rect = mount.getBoundingClientRect()
      mouse.x = ((event.clientX - rect.left) / mount.clientWidth) * 2 - 1
      mouse.y = -((event.clientY - rect.top) / mount.clientHeight) * 2 + 1

      if (isLandingAnimationActive) {
        hovered = null
        tooltip.style.opacity = '0'
        return
      }

      targetRotationY = -0.45 + mouse.x * 0.35
      targetRotationX = 0.35 - mouse.y * 0.2
      raycaster.setFromCamera(mouse, camera)
      const hits = raycaster.intersectObjects(pancakeMeshes)
      if (hits.length > 0) {
        const hit = hits[0].object as THREE.Mesh
        if (hovered !== hit) {
          hovered = hit
          showTooltip(hit, event.clientX - rect.left, event.clientY - rect.top)
        } else {
          tooltip.style.left = `${Math.min(event.clientX - rect.left + 15, mount.clientWidth - 270)}px`
          tooltip.style.top = `${Math.max(event.clientY - rect.top - 30, 20)}px`
        }
      } else {
        hovered = null
        tooltip.style.opacity = '0'
      }
    }

    function onClick() {
      if (isLandingAnimationActive) return
      raycaster.setFromCamera(mouse, camera)
      const hits = raycaster.intersectObjects(pancakeMeshes)
      if (hits.length > 0) {
        onSelectRef.current((hits[0].object.userData as PancakeUserData).cve.id)
      }
    }

    function onResize() {
      if (!mount) return
      camera.aspect = mount.clientWidth / Math.max(mount.clientHeight, 1)
      camera.updateProjectionMatrix()
      renderer.setSize(mount.clientWidth, mount.clientHeight)
    }

    let raf = 0
    function animate() {
      if (disposed) return
      raf = requestAnimationFrame(animate)
      const dt = Math.min(clock.getDelta(), 0.05)
      updatePhysicsAndAnimations(dt)

      const shakeX = (Math.random() - 0.5) * cameraShake
      const shakeY = (Math.random() - 0.5) * cameraShake

      if (isLandingAnimationActive) {
        const holdX = -0.45
        const holdY = -0.35
        camBase.x += (Math.sin(holdX) * camOrbitRadius - camBase.x) * 0.1
        camBase.y += (camOrbitY + Math.sin(holdY) * 1.15 - camBase.y) * 0.1
        camBase.z += (Math.cos(holdX) * camOrbitRadius - camBase.z) * 0.1
      } else {
        camBase.x += (Math.sin(targetRotationY) * camOrbitRadius - camBase.x) * 0.05
        camBase.y += (camOrbitY + Math.sin(targetRotationX) * 1.15 - camBase.y) * 0.05
        camBase.z += (Math.cos(targetRotationY) * camOrbitRadius - camBase.z) * 0.05
      }
      camera.position.set(camBase.x + shakeX, camBase.y + shakeY, camBase.z)
      camera.lookAt(camLookAt)
      renderer.render(scene, camera)
    }

    mount.addEventListener('mousemove', onMouseMove)
    mount.addEventListener('click', onClick)
    window.addEventListener('resize', onResize)
    animate()

    return () => {
      disposed = true
      cancelAnimationFrame(raf)
      mount.removeEventListener('mousemove', onMouseMove)
      mount.removeEventListener('click', onClick)
      window.removeEventListener('resize', onResize)
      apiRef.current = null
      clearStack()
      textureCache.forEach((t) => t.dispose())
      ;[...new Set(materialCache)].forEach((m) => m.dispose())
      renderer.dispose()
      if (renderer.domElement.parentElement === mount) mount.removeChild(renderer.domElement)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps -- scene bootstraps once; updates via apiRef
  }, [])

  useEffect(() => {
    apiRef.current?.rebuild(stack)
  }, [stack])

  useEffect(() => {
    apiRef.current?.setSelected(selectedId)
  }, [selectedId])

  useEffect(() => {
    apiRef.current?.setFilter(filterTier)
  }, [filterTier])

  return (
    <div className="canvas-mount" ref={mountRef}>
      <div
        ref={tooltipRef}
        className="pointer-events-none absolute z-20 max-w-[260px] rounded-xl border border-[#8B3A0F]/40 bg-[#1E1611]/95 px-3.5 py-2 text-xs text-white opacity-0 shadow-xl backdrop-blur-md transition-opacity duration-200"
      >
        <div className="flex items-center justify-between font-bold text-[#F5A623]">
          <span data-tip-id>CVE</span>
          <span data-tip-pri className="rounded px-1.5 py-0.5 font-mono text-[10px]">
            P0
          </span>
        </div>
        <div data-tip-name className="mt-0.5 text-[11px] text-[#D6C7B2]" />
        <div className="mt-1 font-mono text-[10px] text-amber-300/90">Click layer to inspect deep dive →</div>
      </div>
    </div>
  )
}
