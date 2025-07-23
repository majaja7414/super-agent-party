export async function fetchLanguage() {
    try {
        const http_protocol = window.location.protocol;
        const HOST = window.location.host;
        let res = await fetch(`${http_protocol}//${HOST}/cur_language`);
        const data = await res.json();
        return data.language;
    } catch (error) {
        console.error('Error fetching language:', error);
        return 'zh-CN';
    }
}

export async function t(key) {
    const currentLanguage = await fetchLanguage();
    return translations[currentLanguage][key] || key;
}

export async function fetchVRMConfig() {
    try {
        const http_protocol = window.location.protocol;
        const HOST = window.location.host;
        let res = await fetch(`${http_protocol}//${HOST}/vrm_config`);
        const data = await res.json();
        return data.VRMConfig;
    } catch (error) {
        console.error('Error fetching VRMConfig:', error);
        return {
            enabledExpressions: false,
            selectedModelId: 'alice',
            defaultModels: [],
            userModels: []
        };
    }
}

export async function getVRMpath() {
    const vrmConfig = await fetchVRMConfig();
    const modelId = vrmConfig.selectedModelId;
    const defaultModel = vrmConfig.defaultModels.find(model => model.id === modelId) ||
        vrmConfig.userModels.find(model => model.id === modelId);
    if (defaultModel) {
        return defaultModel.path;
    } else {
        const userModel = vrmConfig.userModels.find(model => model.id === modelId);
        if (userModel) {
            return userModel.path;
        }
        return 'http://127.0.0.1:3456/vrm/Alice.vrm';
    }
}

export function setNaturalPose(vrm) {
    if (!vrm.humanoid) return;
    vrm.humanoid.getNormalizedBoneNode('leftUpperArm').rotation.z = -0.4 * Math.PI;
    vrm.humanoid.getNormalizedBoneNode('rightUpperArm').rotation.z = 0.4 * Math.PI;
    const leftHand = vrm.humanoid.getNormalizedBoneNode('leftHand');
    if (leftHand) {
        leftHand.rotation.z = 0.1;
        leftHand.rotation.x = 0.05;
    }
    const rightHand = vrm.humanoid.getNormalizedBoneNode('rightHand');
    if (rightHand) {
        rightHand.rotation.z = -0.1;
        rightHand.rotation.x = 0.05;
    }
    const fingerBones = [
        'leftThumbProximal', 'leftThumbIntermediate', 'leftThumbDistal',
        'leftIndexProximal', 'leftIndexIntermediate', 'leftIndexDistal',
        'leftMiddleProximal', 'leftMiddleIntermediate', 'leftMiddleDistal',
        'leftRingProximal', 'leftRingIntermediate', 'leftRingDistal',
        'leftLittleProximal', 'leftLittleIntermediate', 'leftLittleDistal',
        'rightThumbProximal', 'rightThumbIntermediate', 'rightThumbDistal',
        'rightIndexProximal', 'rightIndexIntermediate', 'rightIndexDistal',
        'rightMiddleProximal', 'rightMiddleIntermediate', 'rightMiddleDistal',
        'rightRingProximal', 'rightRingIntermediate', 'rightRingDistal',
        'rightLittleProximal', 'rightLittleIntermediate', 'rightLittleDistal'
    ];
    fingerBones.forEach(boneName => {
        const bone = vrm.humanoid.getNormalizedBoneNode(boneName);
        if (bone) {
            if (boneName.includes('Thumb')) {
                bone.rotation.y = boneName.includes('left') ? 0.35 : -0.35;
            } else if (boneName.includes('Proximal')) {
                bone.rotation.z = boneName.includes('left') ? -0.35 : 0.35;
            } else if (boneName.includes('Intermediate')) {
                bone.rotation.z = boneName.includes('left') ? -0.45 : 0.45;
            } else if (boneName.includes('Distal')) {
                bone.rotation.z = boneName.includes('left') ? -0.3 : 0.3;
            }
        }
    });
}

export function getRandomBlinkData() {
    const interval = Math.random() * 4 + 1.5;
    const pattern = Math.random() < 0.8 ? 0 : 1;
    return { interval, pattern };
}

export function applyIdleAnimation(vrm, time, idleOffsets) {
    if (!vrm.humanoid) return;
    const bodySwayX = Math.sin(time * 0.3 + idleOffsets.body) * 0.02;
    const bodySwayZ = Math.cos(time * 0.25 + idleOffsets.body) * 0.015;
    const spine = vrm.humanoid.getNormalizedBoneNode('spine');
    if (spine) {
        spine.rotation.x = bodySwayX;
        spine.rotation.z = bodySwayZ;
    }
    const chest = vrm.humanoid.getNormalizedBoneNode('chest');
    if (chest) {
        chest.rotation.x = bodySwayX * 0.5;
        chest.rotation.z = bodySwayZ * 0.5;
    }
    const leftUpperArm = vrm.humanoid.getNormalizedBoneNode('leftUpperArm');
    const leftLowerArm = vrm.humanoid.getNormalizedBoneNode('leftLowerArm');
    if (leftUpperArm) {
        leftUpperArm.rotation.z = -0.43 * Math.PI + Math.sin(time * 0.75 + idleOffsets.leftArm) * 0.03 - 0.01;
        leftUpperArm.rotation.x = Math.cos(time * 0.35 + idleOffsets.leftArm) * 0.03;
        leftUpperArm.rotation.y = Math.sin(time * 0.3 + idleOffsets.leftArm) * 0.02;
    }
    if (leftLowerArm) {
        leftLowerArm.rotation.z = -Math.sin(time * 0.75 + idleOffsets.leftArm) * 0.02;
    }
    const rightUpperArm = vrm.humanoid.getNormalizedBoneNode('rightUpperArm');
    const rightLowerArm = vrm.humanoid.getNormalizedBoneNode('rightLowerArm');
    if (rightUpperArm) {
        rightUpperArm.rotation.z = 0.43 * Math.PI + Math.sin(time * 0.75 + idleOffsets.rightArm) * 0.03;
        rightUpperArm.rotation.x = Math.cos(time * 0.4 + idleOffsets.rightArm) * 0.03;
        rightUpperArm.rotation.y = Math.sin(time * 0.32 + idleOffsets.rightArm) * 0.02;
    }
    if (rightLowerArm) {
        rightLowerArm.rotation.z = -Math.sin(time * 0.75 + idleOffsets.rightArm) * 0.02;
    }
    const leftHand = vrm.humanoid.getNormalizedBoneNode('leftHand');
    if (leftHand) {
        leftHand.rotation.z = 0.1 + Math.sin(time * 0.6 + idleOffsets.leftArm) * 0.015;
        leftHand.rotation.x = 0.05;
    }
    const rightHand = vrm.humanoid.getNormalizedBoneNode('rightHand');
    if (rightHand) {
        rightHand.rotation.z = -0.1 - Math.sin(time * 0.6 + idleOffsets.rightArm) * 0.015;
        rightHand.rotation.x = 0.05;
    }
    const headBone = vrm.humanoid.getNormalizedBoneNode('head');
    if (headBone) {
        headBone.rotation.y = Math.sin(time * 0.7 + idleOffsets.head) * 0.03;
        headBone.rotation.x = Math.sin(time * 0.5 + idleOffsets.head) * 0.02;
        headBone.rotation.z = Math.cos(time * 0.4 + idleOffsets.head) * 0.01;
    }
    const leftShoulder = vrm.humanoid.getNormalizedBoneNode('leftShoulder');
    const rightShoulder = vrm.humanoid.getNormalizedBoneNode('rightShoulder');
    if (leftShoulder) {
        leftShoulder.rotation.z = Math.sin(time * 0.35 + idleOffsets.leftArm) * 0.02;
    }
    if (rightShoulder) {
        rightShoulder.rotation.z = Math.sin(time * 0.4 + idleOffsets.rightArm) * 0.02;
    }
    const neck = vrm.humanoid.getNormalizedBoneNode('neck');
    if (neck) {
        neck.rotation.y = Math.sin(time * 0.7 + idleOffsets.head) * 0.02;
        neck.rotation.x = Math.cos(time * 0.6 + idleOffsets.head) * 0.01;
    }
}