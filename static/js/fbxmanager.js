import { FBXLoader } from 'three/addons/loaders/FBXLoader.js';
import { remapMixamoAnimationToVrm } from './remapMixamoAnimationToVrm.js';

const FBX_BASE = new URL('../fbx/', import.meta.url).href;

const ANIMATIONS = [
  { name: 'Idle', file: 'Idle.fbx' },
  { name: 'Walking', file: 'Walking.fbx' },
  { name: 'Dancing', file: 'Dance.fbx' },
];

export async function loadAnimationsForVrm(vrm) {
  const loader = new FBXLoader();
  const clips = [];

  for (const anim of ANIMATIONS) {
    const fbx = await loader.loadAsync(`${FBX_BASE}${anim.file}`);
    const clip = remapMixamoAnimationToVrm(vrm, fbx);
    clip.name = anim.name;
    clips.push(clip);
  }

  return clips;
}