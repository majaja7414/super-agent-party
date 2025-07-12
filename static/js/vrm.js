import * as THREE from 'three/webgpu';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { VRMLoaderPlugin, MToonMaterialLoaderPlugin, VRMUtils, VRMLookAt } from '@pixiv/three-vrm';
import { MToonNodeMaterial } from '@pixiv/three-vrm/nodes';

const _v3A = new THREE.Vector3();

// extended lookat
class VRMSmoothLookAt extends VRMLookAt {

    constructor( humanoid, applier ) {

        super( humanoid, applier );

        // a factor used for animation
        this.smoothFactor = 10.0;

        // maximum angles the lookAt tracks
        this.yawLimit = 45.0;
        this.pitchLimit = 45.0;

        // Actual angles applied, animated
        this._yawDamped = 0.0;
        this._pitchDamped = 0.0;

    }

    update( delta ) {

        if ( this.target && this.autoUpdate ) {

            // this updates `_yaw` and `_pitch`
            this.lookAt( this.target.getWorldPosition( _v3A ) );

            // limit angles
            if (

                this.yawLimit < Math.abs( this._yaw ) ||
                this.pitchLimit < Math.abs( this._pitch )

            ) {

                this._yaw = 0.0;
                this._pitch = 0.0;

            }

            // animate angles
            const k = 1.0 - Math.exp( - this.smoothFactor * delta );

            this._yawDamped += ( this._yaw - this._yawDamped ) * k;
            this._pitchDamped += ( this._pitch - this._pitchDamped ) * k;

            // apply the animated angles
            this.applier.applyYawPitch( this._yawDamped, this._pitchDamped );

            // there is no need to update twice
            this._needsUpdate = false;

        }

        // usual update procedure
        if ( this._needsUpdate ) {

            this._needsUpdate = false;

            this.applier.applyYawPitch( this._yaw, this._pitch );

        }

    }

}

// renderer
// 检测运行环境
const isElectron = typeof require !== 'undefined' || navigator.userAgent.includes('Electron');

// 根据环境添加 class
document.body.classList.add(isElectron ? 'electron' : 'web');

// 优化渲染器设置
const renderer = new THREE.WebGPURenderer({
    alpha: isElectron,
    premultipliedAlpha: isElectron,
    antialias: true,  // 添加抗锯齿
    powerPreference: "high-performance",  // 使用高性能GPU
    forceWebGL: false  // 确保使用WebGPU
});

// 添加性能优化设置
renderer.setSize(window.innerWidth, window.innerHeight);
renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2)); // 限制像素比例
renderer.setClearColor(isElectron ? 0x00000000 : 0xffffff, isElectron ? 0 : 1);

// 用fetch查询/cur_language的值
async function fetchLanguage() {
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
async function t(key) {
    const currentLanguage = await fetchLanguage();
    return translations[currentLanguage][key] || key;
}
// 用fetch查询/cur_language的值
async function fetchVRMConfig() {
    try {
        const http_protocol = window.location.protocol;
        const HOST = window.location.host;
        let res = await fetch(`${http_protocol}//${HOST}/vrm_config`);
        const data = await res.json();
        return data.VRMConfig;
    } catch (error) {
        console.error('Error fetching VRMConfig:', error);
        return   {
            enabledExpressions: false,
            selectedModelId: 'alice', // 默认选择Alice模型
            defaultModels: [], // 存储默认模型
            userModels: []     // 存储用户上传的模型
        };
    }
}

async function getVRMpath() {
    const vrmConfig = await fetchVRMConfig();
    const modelId = vrmConfig.selectedModelId;
    const defaultModel = vrmConfig.defaultModels.find(model => model.id === modelId) || vrmConfig.userModels.find(model => model.id === modelId);
    if (defaultModel) {
        return defaultModel.path;
    } else {
        const userModel = vrmConfig.userModels.find(model => model.id === modelId);
        if (userModel) {
            return userModel.path;
        }
        else {
            return 'http://127.0.0.1:3456/vrm/Alice.vrm';
        }
    }
}

const vrmPath = await getVRMpath();
console.log(vrmPath);

// 启用阴影（如果需要）
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.PCFSoftShadowMap;

document.body.appendChild( renderer.domElement );

// camera
const camera = new THREE.PerspectiveCamera( 30.0, window.innerWidth / window.innerHeight, 0.1, 20.0 );
camera.position.set( 0.0, 1.0, 5.0 );

// camera controls
const controls = new OrbitControls( camera, renderer.domElement );
controls.screenSpacePanning = true;
controls.target.set( 0.0, 1.0, 0.0 );
controls.update();

// scene
const scene = new THREE.Scene();

// 创建地板 - 自发光白色材质
const floorGeometry = new THREE.PlaneGeometry( 20, 20 );
const floorMaterial = new THREE.MeshStandardMaterial( { 
    color: 0xffffff,        // 纯白色
    metalness: 0.1,         
    roughness: 0.1,         
    side: THREE.DoubleSide,
    emissive: 0xffffff,     // 添加自发光
    emissiveIntensity: 0.3  // 自发光强度
} );

// 修改地板材质（仅在 Electron 中隐藏地板）
if (isElectron) {
    floorMaterial.visible = false;
    floorMaterial.opacity = 0;
    floorMaterial.transparent = true;
}
const floor = new THREE.Mesh( floorGeometry, floorMaterial );
floor.rotation.x = -Math.PI / 2;
floor.position.y = 0;
scene.add( floor );

// light
const light = new THREE.DirectionalLight( 0xffffff, Math.PI );
light.position.set( 1.0, 1.0, 1.0 ).normalize();
scene.add( light );

// 添加环境光，让整体更柔和
const ambientLight = new THREE.AmbientLight( 0xffffff, 0.3 );
scene.add( ambientLight );

// gltf and vrm
let currentVrm = undefined;
const loader = new GLTFLoader();
loader.crossOrigin = 'anonymous';

loader.register( ( parser ) => {
    // 创建 WebGPU 兼容的 MToonMaterialLoaderPlugin
    const mtoonMaterialPlugin = new MToonMaterialLoaderPlugin( parser, {
        materialType: MToonNodeMaterial,
    } );

    return new VRMLoaderPlugin( parser, {
        mtoonMaterialPlugin,
        // 确保启用所有功能
        autoUpdateHumanBones: true,
    } );
} );

// 设置自然姿势的函数
function setNaturalPose(vrm) {
    if (!vrm.humanoid) return;

    // 左臂自然下垂
    vrm.humanoid.getNormalizedBoneNode( 'leftUpperArm' ).rotation.z = -0.4 * Math.PI;

    // 右臂自然下垂
    vrm.humanoid.getNormalizedBoneNode( 'rightUpperArm' ).rotation.z = 0.4 * Math.PI;
    
    const leftHand = vrm.humanoid.getNormalizedBoneNode('leftHand');
    if (leftHand) {
        leftHand.rotation.z = 0.1; // 手腕自然弯曲
        leftHand.rotation.x = 0.05;
    }
    const rightHand = vrm.humanoid.getNormalizedBoneNode('rightHand');
    if (rightHand) {
        rightHand.rotation.z = -0.1; // 手腕自然弯曲
        rightHand.rotation.x = 0.05;
    }
    // 添加手指的自然弯曲（如果模型支持）
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
            // 根据手指部位设置不同的弯曲度
            if (boneName.includes('Thumb')) {
                // 拇指稍微向内
                bone.rotation.y = boneName.includes('left') ? 0.35 : -0.35;
            } else if (boneName.includes('Proximal')) {
                // 近端指骨轻微弯曲
                bone.rotation.z = boneName.includes('left') ? -0.35 : 0.35;
            } else if (boneName.includes('Intermediate')) {
                // 中端指骨稍微弯曲
                bone.rotation.z = boneName.includes('left') ? -0.45 : 0.45;
            } else if (boneName.includes('Distal')) {
                // 远端指骨轻微弯曲
                bone.rotation.z = boneName.includes('left') ? -0.3 : 0.3;
            }
        }
    });
}

loader.load(

    // URL of the VRM you want to load
    vrmPath,

    // called when the resource is loaded
    ( gltf ) => {

        const vrm = gltf.userData.vrm;

        // calling these functions greatly improves the performance
        VRMUtils.removeUnnecessaryVertices( gltf.scene );
        VRMUtils.combineSkeletons( gltf.scene );
        VRMUtils.combineMorphs( vrm );

        // 启用 Spring Bone 物理模拟
        if (vrm.springBoneManager) {
            console.log('Spring Bone Manager found:', vrm.springBoneManager);
            // Spring Bone 会在 vrm.update() 中自动更新
        }


        // Disable frustum culling
        vrm.scene.traverse( ( obj ) => {

            obj.frustumCulled = false;

        } );

        // replace the lookAt to our extended one
        if ( vrm.lookAt ) {
            const smoothLookAt = new VRMSmoothLookAt( vrm.humanoid, vrm.lookAt.applier );
            smoothLookAt.copy( vrm.lookAt );
            vrm.lookAt = smoothLookAt;

            // set the lookAt target to camera
            vrm.lookAt.target = camera;
        }

        currentVrm = vrm;
        console.log( vrm );
        scene.add( vrm.scene );

        // 设置自然姿势
        setNaturalPose(vrm);

    },

    // called while loading is progressing
    ( progress ) => console.log( 'Loading model...', 100.0 * ( progress.loaded / progress.total ), '%' ),

    // called when loading has errors
    ( error ) => console.error( error )

);

// animate
const clock = new THREE.Clock();
clock.start();

// 在全局变量区域添加眨眼相关的变量
let nextBlinkTime = 0;
let isBlinking = false;
let blinkStartTime = 0;
let blinkPattern = 0; // 0: 单次眨眼, 1: 双次眨眼
const singleBlinkDuration = 0.15;
const doubleBlinkDuration = 0.4;

// 闲置动作的时间偏移量，让各个动作不同步
const idleOffsets = {
    body: Math.random() * Math.PI * 2,
    leftArm: Math.random() * Math.PI * 2,
    rightArm: Math.random() * Math.PI * 2,
    head: Math.random() * Math.PI * 2,
    spine: Math.random() * Math.PI * 2
};

// 生成随机的下次眨眼时间和模式
function getRandomBlinkData() {
    const interval = Math.random() * 4 + 1.5; // 1.5-5.5秒之间的随机间隔
    const pattern = Math.random() < 0.8 ? 0 : 1; // 80%单次眨眼，20%双次眨眼
    return { interval, pattern };
}

// 闲置动作函数
function applyIdleAnimation(vrm, time) {
    if (!vrm.humanoid) return;

    // 身体轻微摆动 - 慢速，小幅度
    const bodySwayX = Math.sin(time * 0.3 + idleOffsets.body) * 0.02;
    const bodySwayZ = Math.cos(time * 0.25 + idleOffsets.body) * 0.015;
    
    // 脊椎轻微摆动
    const spine = vrm.humanoid.getNormalizedBoneNode('spine');
    if (spine) {
        spine.rotation.x = bodySwayX;
        spine.rotation.z = bodySwayZ;
    }

    // 胸部轻微摆动
    const chest = vrm.humanoid.getNormalizedBoneNode('chest');
    if (chest) {
        chest.rotation.x = bodySwayX * 0.5;
        chest.rotation.z = bodySwayZ * 0.5;
    }

    // 左臂自然摆动
    const leftUpperArm = vrm.humanoid.getNormalizedBoneNode('leftUpperArm');
    const leftLowerArm = vrm.humanoid.getNormalizedBoneNode('leftLowerArm');
    if (leftUpperArm) {
        // 保持基本姿势，添加轻微摆动
        leftUpperArm.rotation.z = -0.43 * Math.PI + Math.sin(time * 0.75 + idleOffsets.leftArm) * 0.03 - 0.01;
        leftUpperArm.rotation.x = Math.cos(time * 0.35 + idleOffsets.leftArm) * 0.03;
        leftUpperArm.rotation.y = Math.sin(time * 0.3 + idleOffsets.leftArm) * 0.02;
    }
    if (leftLowerArm) {
        leftLowerArm.rotation.z = - Math.sin(time * 0.75 + idleOffsets.leftArm) * 0.02;
    }

    // 右臂自然摆动
    const rightUpperArm = vrm.humanoid.getNormalizedBoneNode('rightUpperArm');
    const rightLowerArm = vrm.humanoid.getNormalizedBoneNode('rightLowerArm');
    if (rightUpperArm) {
        // 保持基本姿势，添加轻微摆动
        rightUpperArm.rotation.z = 0.43 * Math.PI + Math.sin(time * 0.75 + idleOffsets.rightArm) * 0.03;
        rightUpperArm.rotation.x = Math.cos(time * 0.4 + idleOffsets.rightArm) * 0.03;
        rightUpperArm.rotation.y = Math.sin(time * 0.32 + idleOffsets.rightArm) * 0.02;
    }
    if (rightLowerArm) {
        rightLowerArm.rotation.z = - Math.sin(time * 0.75 + idleOffsets.rightArm) * 0.02;
    }

    const leftHand = vrm.humanoid.getNormalizedBoneNode('leftHand');
    if (leftHand) {
        leftHand.rotation.z = 0.1 + Math.sin(time * 0.6 + idleOffsets.leftArm) * 0.015; // 手腕自然弯曲
        leftHand.rotation.x = 0.05;
    }
    const rightHand = vrm.humanoid.getNormalizedBoneNode('rightHand');
    if (rightHand) {
        rightHand.rotation.z = -0.1 - Math.sin(time * 0.6 + idleOffsets.rightArm) * 0.015; // 手腕自然弯曲
        rightHand.rotation.x = 0.05;
    }

    // 头部轻微摆动 - 比原来更细腻
    const headBone = vrm.humanoid.getNormalizedBoneNode('head');
    if (headBone) {
        headBone.rotation.y = Math.sin(time * 0.7 + idleOffsets.head) * 0.03;
        headBone.rotation.x = Math.sin(time * 0.5 + idleOffsets.head) * 0.02;
        headBone.rotation.z = Math.cos(time * 0.4 + idleOffsets.head) * 0.01;
    }

    // 肩膀轻微摆动
    const leftShoulder = vrm.humanoid.getNormalizedBoneNode('leftShoulder');
    const rightShoulder = vrm.humanoid.getNormalizedBoneNode('rightShoulder');
    if (leftShoulder) {
        leftShoulder.rotation.z = Math.sin(time * 0.35 + idleOffsets.leftArm) * 0.02;
    }
    if (rightShoulder) {
        rightShoulder.rotation.z = Math.sin(time * 0.4 + idleOffsets.rightArm) * 0.02;
    }

    // 颈部轻微摆动
    const neck = vrm.humanoid.getNormalizedBoneNode('neck');
    if (neck) {
        neck.rotation.y = Math.sin(time * 0.7 + idleOffsets.head) * 0.02;
        neck.rotation.x = Math.cos(time * 0.6 + idleOffsets.head) * 0.01;
    }
}

// 在animate函数中替换原来的眨眼动画代码
function animate() {
    requestAnimationFrame(animate);
    
    const time = clock.getElapsedTime();
    const deltaTime = clock.getDelta();
    
    if (currentVrm) {
        // 简单的呼吸动画 - 更自然的呼吸节奏
        const breathScale = 1 + Math.sin(time * 1.5) * 0.003;
        currentVrm.scene.scale.setScalar(breathScale);
        
        // 应用闲置动作
        applyIdleAnimation(currentVrm, time);
        
        // 高级随机眨眼动画
        if (currentVrm.expressionManager) {
            if (!isBlinking && time >= nextBlinkTime) {
                // 开始眨眼
                isBlinking = true;
                blinkStartTime = time;
                const blinkData = getRandomBlinkData();
                nextBlinkTime = time + blinkData.interval;
                blinkPattern = blinkData.pattern;
            }
            
            if (isBlinking) {
                const blinkElapsed = time - blinkStartTime;
                const duration = blinkPattern === 0 ? singleBlinkDuration : doubleBlinkDuration;
                
                if (blinkElapsed < duration) {
                    let blinkValue = 0;
                    
                    if (blinkPattern === 0) {
                        // 单次眨眼
                        const progress = blinkElapsed / duration;
                        blinkValue = Math.sin(progress * Math.PI);
                    } else {
                        // 双次眨眼
                        const progress = blinkElapsed / duration;
                        if (progress < 0.4) {
                            // 第一次眨眼
                            blinkValue = Math.sin((progress / 0.4) * Math.PI);
                        } else if (progress < 0.6) {
                            // 间隔
                            blinkValue = 0;
                        } else {
                            // 第二次眨眼
                            blinkValue = Math.sin(((progress - 0.6) / 0.4) * Math.PI);
                        }
                    }
                    
                    currentVrm.expressionManager.setValue('blink', blinkValue);
                } else {
                    // 眨眼结束
                    isBlinking = false;
                    currentVrm.expressionManager.setValue('blink', 0.0);
                }
            }
        }
        
        // 更新VRM，包括lookAt动画
        currentVrm.update(deltaTime);
    }
    
    renderer.renderAsync(scene, camera);
}

// 初始化第一次眨眼时间
const initialBlinkData = getRandomBlinkData();
nextBlinkTime = initialBlinkData.interval;

if (isElectron) {
    // 等待一小段时间确保页面完全加载
    setTimeout(() => {
        // 创建控制面板容器
        const controlPanel = document.createElement('div');
        controlPanel.id = 'control-panel';
        controlPanel.style.cssText = `
        position: fixed;
        top: 10px;
        right: 10px;
        display: flex;
        flex-direction: column;
        gap: 8px;
        z-index: 9999;
        opacity: 0;
        visibility: hidden;
        transform: translateX(20px);
        transition: all 0.3s ease;
        pointer-events: none;
        `;
        
        // 拖拽按钮
        const dragButton = document.createElement('div');
        dragButton.id = 'drag-handle';
        dragButton.innerHTML = '<i class="fas fa-grip-vertical"></i>';
        dragButton.style.cssText = `
                width: 36px;
                height: 36px;
                background: rgba(255,255,255,0.95);
                border: 2px solid rgba(0,0,0,0.1);
                border-radius: 50%;
                color: #333;
                cursor: pointer;
                -webkit-app-region: drag;
                display: flex;
                align-items: center;
                justify-content: center;
                font-size: 14px;
                box-shadow: 0 4px 12px rgba(0,0,0,0.15);
                transition: all 0.2s ease;
                user-select: none;
                pointer-events: auto;
                backdrop-filter: blur(10px);
        `;

        // 创建一个内部拖拽区域来确保拖拽功能正常
        const dragArea = document.createElement('div');
        dragArea.style.cssText = `
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            -webkit-app-region: drag;
            z-index: 1;
        `;

        // 图标容器
        const iconContainer = document.createElement('div');
        iconContainer.innerHTML = '<i class="fas fa-grip-vertical"></i>';
        iconContainer.style.cssText = `
            position: relative;
            z-index: 2;
            pointer-events: none;
            display: flex;
            align-items: center;
            justify-content: center;
            width: 100%;
            height: 100%;
            -webkit-app-region: drag;
        `;

        // 组装拖拽按钮
        dragButton.innerHTML = '';
        dragButton.appendChild(dragArea);
        dragButton.appendChild(iconContainer);
        
        // 刷新按钮
        const refreshButton = document.createElement('div');
        refreshButton.id = 'refresh-handle';
        refreshButton.innerHTML = '<i class="fas fa-redo-alt"></i>';
        refreshButton.style.cssText = `
                width: 36px;
                height: 36px;
                background: rgba(255,255,255,0.95);
                border: 2px solid rgba(0,0,0,0.1);
                border-radius: 50%;
                color: #333;
                cursor: pointer;
                -webkit-app-region: no-drag;
                display: flex;
                align-items: center;
                justify-content: center;
                font-size: 14px;
                box-shadow: 0 4px 12px rgba(0,0,0,0.15);
                transition: all 0.2s ease;
                user-select: none;
                pointer-events: auto;
                backdrop-filter: blur(10px);
        `;
        
        // 关闭按钮
        const closeButton = document.createElement('div');
        closeButton.id = 'close-handle';
        closeButton.innerHTML = '<i class="fas fa-times"></i>';
        closeButton.style.cssText = `
                width: 36px;
                height: 36px;
                background: rgba(255,255,255,0.95);
                border: 2px solid rgba(0,0,0,0.1);
                border-radius: 50%;
                color: #333;
                cursor: pointer;
                -webkit-app-region: no-drag;
                display: flex;
                align-items: center;
                justify-content: center;
                font-size: 14px;
                box-shadow: 0 4px 12px rgba(0,0,0,0.15);
                transition: all 0.2s ease;
                user-select: none;
                pointer-events: auto;
                backdrop-filter: blur(10px);
        `;
        
        // 添加悬停效果 - 刷新按钮
        refreshButton.addEventListener('mouseenter', () => {
            refreshButton.style.background = 'rgba(255,255,255,1)';
            refreshButton.style.transform = 'scale(1.1)';
            refreshButton.style.boxShadow = '0 6px 16px rgba(0,0,0,0.2)';
        });
        
        refreshButton.addEventListener('mouseleave', () => {
            refreshButton.style.background = 'rgba(255,255,255,0.95)';
            refreshButton.style.transform = 'scale(1)';
            refreshButton.style.boxShadow = '0 4px 12px rgba(0,0,0,0.15)';
        });

        // 刷新按钮点击事件
        refreshButton.addEventListener('click', (e) => {
            e.preventDefault();
            e.stopPropagation();
            // 刷新页面
            window.location.reload();
        });
        
        // 添加悬停效果 - 关闭按钮
        closeButton.addEventListener('mouseenter', () => {
            closeButton.style.background = 'rgba(255,255,255,1)';
            closeButton.style.transform = 'scale(1.1)';
            closeButton.style.boxShadow = '0 6px 16px rgba(0,0,0,0.2)';
        });
        
        closeButton.addEventListener('mouseleave', () => {
            closeButton.style.background = 'rgba(255,255,255,0.95)';
            closeButton.style.transform = 'scale(1)';
            closeButton.style.boxShadow = '0 4px 12px rgba(0,0,0,0.15)';
        });

        // 关闭按钮点击事件
        closeButton.addEventListener('click', (e) => {
            e.preventDefault();
            e.stopPropagation();
            if (window.electronAPI && window.electronAPI.stopVRMWindow) {
                window.electronAPI.stopVRMWindow();
            } else {
                // 备用方案：直接关闭窗口
                window.close();
            }
        });
        async function initbutton() {
            dragButton.title = await t('dragWindow');
            refreshButton.title = await t('refreshWindow');
            closeButton.title = await t('closeWindow');
        }
        initbutton();
        // 组装控制面板
        controlPanel.appendChild(dragButton);
        controlPanel.appendChild(refreshButton);
        controlPanel.appendChild(closeButton);
        
        // 添加到页面
        document.body.appendChild(controlPanel);
        
        // 显示/隐藏控制逻辑
        let hideTimeout;
        let isControlPanelHovered = false;
        
        // 显示控制面板
        function showControlPanel() {
            clearTimeout(hideTimeout);
            controlPanel.style.opacity = '1';
            controlPanel.style.visibility = 'visible';
            controlPanel.style.transform = 'translateX(0)';
            controlPanel.style.pointerEvents = 'auto';
        }
        
        // 隐藏控制面板
        function hideControlPanel() {
            if (!isControlPanelHovered) {
                controlPanel.style.opacity = '0';
                controlPanel.style.visibility = 'hidden';
                controlPanel.style.transform = 'translateX(20px)';
                controlPanel.style.pointerEvents = 'none';
            }
        }
        
        // 延迟隐藏控制面板
        function scheduleHide() {
            clearTimeout(hideTimeout);
            hideTimeout = setTimeout(hideControlPanel, 2000); // 2秒后隐藏
        }
        
        // 窗口鼠标进入事件
        document.body.addEventListener('mouseenter', () => {
            showControlPanel();
        });
        
        // 窗口鼠标移动事件（重置隐藏计时器）
        document.body.addEventListener('mousemove', () => {
            showControlPanel();
            scheduleHide();
        });
        
        // 窗口鼠标离开事件
        document.body.addEventListener('mouseleave', () => {
            if (!isControlPanelHovered) {
                scheduleHide();
            }
        });
        
        // 控制面板鼠标进入事件
        controlPanel.addEventListener('mouseenter', () => {
            isControlPanelHovered = true;
            clearTimeout(hideTimeout);
            showControlPanel();
        });
        
        // 控制面板鼠标离开事件
        controlPanel.addEventListener('mouseleave', () => {
            isControlPanelHovered = false;
            scheduleHide();
        });
        
        // 鼠标静止检测
        let mouseStopTimeout;
        document.body.addEventListener('mousemove', () => {
            clearTimeout(mouseStopTimeout);
            mouseStopTimeout = setTimeout(() => {
                if (!isControlPanelHovered) {
                    hideControlPanel();
                }
            }, 3000); // 鼠标静止3秒后隐藏
        });
        
        // 初始状态：隐藏控制面板
        scheduleHide();
        
        console.log('控制面板已添加到页面');
    }, 1000);
}

// 在全局变量区域添加
let ttsWebSocket = null;
let wsConnected = false;
let currentAudioContext = null;
let currentAnalyser = null;
let currentAudioSource = null;
let isCurrentlySpeaking = false;
let lipSyncAnimationId = null;


// 初始化 WebSocket 连接
function initTTSWebSocket() {
    const http_protocol = window.location.protocol;
    const ws_protocol = http_protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${ws_protocol}//${window.location.host}/ws/vrm`;
    ttsWebSocket = new WebSocket(wsUrl);
    
    ttsWebSocket.onopen = () => {
        console.log('VRM TTS WebSocket connected');
        wsConnected = true;
        
        // 发送连接确认
        sendToMain('vrmConnected', { status: 'ready' });
    };
    
    ttsWebSocket.onmessage = (event) => {
        try {
            const message = JSON.parse(event.data);
            handleTTSMessage(message);
        } catch (error) {
            console.error('Error parsing WebSocket message:', error);
        }
    };
    
    ttsWebSocket.onclose = () => {
        console.log('VRM TTS WebSocket disconnected');
        wsConnected = false;
        
        // 停止当前的说话动画
        stopLipSync();
        
        // 自动重连
        setTimeout(() => {
            if (!wsConnected) {
                initTTSWebSocket();
            }
        }, 3000);
    };
    
    ttsWebSocket.onerror = (error) => {
        console.error('VRM TTS WebSocket error:', error);
    };
}
initTTSWebSocket();
// 发送消息到主界面
function sendToMain(type, data) {
    if (ttsWebSocket && wsConnected) {
        ttsWebSocket.send(JSON.stringify({
            type,
            data,
            timestamp: Date.now()
        }));
    }
}
// 全局变量区域添加
let chunkAnimations = new Map(); // 存储每个chunk的动画状态
let currentChunkIndex = -1;

// 修改 handleTTSMessage 函数
function handleTTSMessage(message) {
    const { type, data } = message;
    
    switch (type) {
        case 'ttsStarted':
            console.log('TTS started, preparing for speech animation');
            // 重置所有状态
            chunkAnimations.clear();
            currentChunkIndex = -1;
            stopLipSync();
            prepareSpeechAnimation(data);
            break;
            
        case 'startSpeaking':
            console.log('Starting speech animation for chunk:', data.chunkIndex);
            currentChunkIndex = data.chunkIndex;
            startLipSyncForChunk(data);
            break;
            
        case 'chunkEnded':
            console.log('Chunk ended:', data.chunkIndex);
            // 停止特定chunk的动画
            stopChunkAnimation(data.chunkIndex);
            break;
            
        case 'stopSpeaking':
            console.log('Stopping speech animation');
            stopAllAnimations();
            break;
            
        case 'allChunksCompleted':
            console.log('All TTS chunks completed');
            stopAllAnimations();
            sendToMain('animationComplete', { status: 'completed' });
            break;
    }
}

// 新的chunk动画管理函数
async function startLipSyncForChunk(data) {
    const chunkId = data.chunkIndex;
    
    // 如果这个chunk已经在播放，先停止它
    if (chunkAnimations.has(chunkId)) {
        stopChunkAnimation(chunkId);
    }
    
    console.log(`Starting lip sync for chunk ${chunkId}`);
    
    if (!currentVrm || !currentVrm.expressionManager) {
        console.error('VRM or expression manager not available');
        return;
    }
    
    try {
        // 创建这个chunk的动画状态
        const chunkState = {
            isPlaying: true,
            animationId: null,
            audio: null,
            audioSource: null,
            analyser: null,
            expression: null,
        };
        
        chunkAnimations.set(chunkId, chunkState);
        
        // 创建音频上下文（如果需要）
        if (!currentAudioContext) {
            currentAudioContext = new (window.AudioContext || window.webkitAudioContext)();
        }
        
        if (currentAudioContext.state === 'suspended') {
            await currentAudioContext.resume();
        }
        // 使用面部表情
        let exp = data.expressions || [];
        if(exp.length > 0){ 
            let cur_exp = exp[0];
            // 移除cur_exp中的<>符号
            cur_exp = cur_exp.replace(/<|>/g, '');
            console.log(`Setting expression to ${cur_exp}`);
            currentVrm.expressionManager.resetValues();
            chunkState.expression = cur_exp;
        }
        console.log(data.expressions);
        // 使用 Base64 数据创建音频
        const audio = new Audio();
        audio.crossOrigin = 'anonymous';
        audio.src = data.audioDataUrl; // 使用 Base64 数据 URL
        audio.volume = 0.01;
        chunkState.audio = audio;
        console.log(`Loading audio for chunk ${chunkId}:`, data.audioUrl);
        
        // 等待音频加载
        await new Promise((resolve, reject) => {
            const timeout = setTimeout(() => {
                reject(new Error(`Audio loading timeout for chunk ${chunkId}`));
            }, 5000);
            
            audio.addEventListener('canplaythrough', () => {
                clearTimeout(timeout);
                console.log(`Audio loaded for chunk ${chunkId}, duration:`, audio.duration);
                resolve();
            });
            
            audio.addEventListener('error', (e) => {
                clearTimeout(timeout);
                console.error(`Audio loading error for chunk ${chunkId}:`, e);
                reject(e);
            });
            
            audio.load();
        });
        
        // 检查chunk是否还应该播放（可能在加载期间被取消了）
        if (!chunkAnimations.has(chunkId) || !chunkAnimations.get(chunkId).isPlaying) {
            console.log(`Chunk ${chunkId} was cancelled during loading`);
            return;
        }
        
        // 创建分析器
        const analyser = currentAudioContext.createAnalyser();
        analyser.fftSize = 512;
        analyser.smoothingTimeConstant = 0.3;
        analyser.minDecibels = -90;
        analyser.maxDecibels = -10;
        chunkState.analyser = analyser;
        
        // 连接音频源
        const audioSource = currentAudioContext.createMediaElementSource(audio);
        audioSource.connect(analyser);
        chunkState.audioSource = audioSource;
        
        console.log(`Starting playback for chunk ${chunkId}`);
        
        // 开始播放
        const playPromise = audio.play();
        if (playPromise !== undefined) {
            await playPromise;
        }
        
        // 开始动画
        startChunkAnimation(chunkId, chunkState);
        
        // 监听音频结束
        audio.addEventListener('ended', () => {
            console.log(`Audio ended for chunk ${chunkId}`);
            setTimeout(() => {
                stopChunkAnimation(chunkId);
            }, 100);
        });
        
    } catch (error) {
        console.error(`Error starting lip sync for chunk ${chunkId}:`, error);
        stopChunkAnimation(chunkId);
    }
}

// 单个chunk的动画循环
function startChunkAnimation(chunkId, chunkState) {
    if (!chunkState || !chunkState.isPlaying || !chunkState.analyser) {
        console.log(`Cannot start animation for chunk ${chunkId}`);
        return;
    }
    
    const dataArray = new Uint8Array(chunkState.analyser.frequencyBinCount);
    let frameCount = 0;
    
    function animateChunk() {
        // 检查chunk状态
        const currentState = chunkAnimations.get(chunkId);
        if (!currentState || !currentState.isPlaying) {
            console.log(`Stopping animation for chunk ${chunkId} - state changed`);
            return;
        }
        
        frameCount++;
        
        // 获取音频数据
        chunkState.analyser.getByteFrequencyData(dataArray);
        
        // 计算强度
        let sum = 0;
        for (let i = 0; i < dataArray.length; i++) {
            sum += dataArray[i];
        }
        const average = sum / dataArray.length;
        const maxValue = Math.max(...dataArray);
        
        // 调试信息
        if (frameCount % 30 === 0) {
            console.log(`Chunk ${chunkId} audio analysis:`, {
                average,
                maxValue,
                intensity: Math.min(average / 50, 1.0)
            });
        }
        
        // 应用口型动画
        if (currentVrm && currentVrm.expressionManager) {
            if(chunkState.expression){
                // 不同表情以不同的方式展现，happy angry sad neutral surprised relaxed blink blinkLeft blinkRight

                if(chunkState.expression == 'happy' ||chunkState.expression == 'angry' ||chunkState.expression == 'sad' ||chunkState.expression == 'neutral' ||chunkState.expression == 'relaxed'){
                    currentVrm.expressionManager.setValue(chunkState.expression,1.0);
                }
                if( chunkState.expression == 'surprised' ){
                    if (frameCount < 30*2) {
                        currentVrm.expressionManager.setValue(chunkState.expression,1.0);
                    }
                    else{
                        currentVrm.expressionManager.setValue(chunkState.expression,0.0);
                    }
                }
                if (chunkState.expression === 'blink' || chunkState.expression === 'blinkLeft' || chunkState.expression === 'blinkRight') {
                    // 第一秒线性闭眼，第二秒线性睁眼
                    const totalFrames = 30; // 假设每秒30帧，总共2秒
                    const halfFrames = totalFrames / 2;
                    let blink_value = 0;
                    if (frameCount < halfFrames) {
                        // 第一秒闭眼
                        blink_value = frameCount / halfFrames;
                    } else {
                        // 第二秒睁眼
                        blink_value = Math.max(1 - ((frameCount - halfFrames) / halfFrames), 0);
                    }

                    currentVrm.expressionManager.setValue(chunkState.expression, blink_value);
                }
            }

            const intensity = Math.min(average / 4, 1.0); // 进一步降低阈值
            if (intensity > 0.02 || maxValue > 5) { // 更敏感的触发条件
                const mouthOpen = Math.min(Math.max(intensity*1.8, 0.1), 0.7); // 确保最小和最大张嘴程度
                currentVrm.expressionManager.setValue('aa', mouthOpen);
                
                // 添加一些变化
                const variation = Math.sin(frameCount * 0.1) * 0.1;
                currentVrm.expressionManager.setValue('ih', Math.max(0, intensity * 0.3 + variation));
                
                if (frameCount % 30 === 0) {
                    console.log(`Chunk ${chunkId} setting mouth:`, { intensity, mouthOpen });
                }
            } else {
                // 渐进式关闭嘴巴，而不是立即重置
                const currentAA = currentVrm.expressionManager.getValue('aa') || 0;
                const currentIH = currentVrm.expressionManager.getValue('ih') || 0;
                
                currentVrm.expressionManager.setValue('aa', Math.max(0, currentAA - 0.05));
                currentVrm.expressionManager.setValue('ih', Math.max(0, currentIH - 0.03));
            }
        }
        
        // 继续动画
        currentState.animationId = requestAnimationFrame(animateChunk);
    }
    
    console.log(`Starting animation loop for chunk ${chunkId}`);
    chunkState.animationId = requestAnimationFrame(animateChunk);
}

// 停止特定chunk的动画
function stopChunkAnimation(chunkId) {
    const chunkState = chunkAnimations.get(chunkId);
    if (!chunkState) return;
    
    console.log(`Stopping animation for chunk ${chunkId}`);
    
    // 停止动画循环
    chunkState.isPlaying = false;
    if (chunkState.animationId) {
        cancelAnimationFrame(chunkState.animationId);
    }
    
    // 停止音频
    if (chunkState.audio) {
        chunkState.audio.pause();
        chunkState.audio = null;
    }
    
    // 断开音频连接
    if (chunkState.audioSource) {
        chunkState.audioSource.disconnect();
        chunkState.audioSource = null;
    }
    
    // 从映射中移除
    chunkAnimations.delete(chunkId);
    
    // 如果没有其他chunk在播放，重置表情
    if (chunkAnimations.size === 0 && currentVrm && currentVrm.expressionManager) {
        setTimeout(() => {
            if (chunkAnimations.size === 0) { // 再次确认没有新的chunk开始
                currentVrm.expressionManager.resetValues();
                console.log('All mouth expressions reset');
            }
        }, 200);
    }
}

// 停止所有动画
function stopAllAnimations() {
    console.log('Stopping all animations');
    
    // 停止所有chunk动画
    for (const chunkId of chunkAnimations.keys()) {
        stopChunkAnimation(chunkId);
    }
    
    // 重置全局状态
    isCurrentlySpeaking = false;
    currentChunkIndex = -1;
    
    // 重置表情
    if (currentVrm && currentVrm.expressionManager) {
        currentVrm.expressionManager.resetValues();
    }
}

// 更新旧的stopLipSync函数以兼容
function stopLipSync() {
    stopAllAnimations();
}

// 准备说话动画
function prepareSpeechAnimation(data) {
    // 可以在这里做一些准备工作，比如调整表情等
    if (currentVrm && currentVrm.expressionManager) {
        // 重置表情
        currentVrm.expressionManager.setValue('aa', 0);
        currentVrm.expressionManager.setValue('ih', 0);
        currentVrm.expressionManager.setValue('ou', 0);
        currentVrm.expressionManager.setValue('ee', 0);
        currentVrm.expressionManager.setValue('oh', 0);
        currentVrm.expressionManager.resetValue('neutral', 1);
    }
}

// 口型动画循环
function startMouthAnimation() {
    console.log('startMouthAnimation called');
    
    if (!isCurrentlySpeaking || !currentVrm || !currentAnalyser) {
        console.log('Animation conditions not met:', {
            isCurrentlySpeaking,
            hasVrm: !!currentVrm,
            hasAnalyser: !!currentAnalyser
        });
        return;
    }
    
    const dataArray = new Uint8Array(currentAnalyser.frequencyBinCount);
    let frameCount = 0;
    
    function animateMouth() {
        if (!isCurrentlySpeaking) {
            console.log('Stopping animation - not speaking');
            return;
        }
        
        frameCount++;
        
        // 获取音频频率数据
        currentAnalyser.getByteFrequencyData(dataArray);
        
        // 计算音频强度
        let sum = 0;
        for (let i = 0; i < dataArray.length; i++) {
            sum += dataArray[i];
        }
        const average = sum / dataArray.length;
        
        // 每30帧打印一次调试信息
        if (frameCount % 30 === 0) {
            console.log('Audio analysis:', {
                average,
                maxValue: Math.max(...dataArray),
                dataArrayLength: dataArray.length,
                hasExpressionManager: !!currentVrm.expressionManager
            });
        }
        
        // 简化的口型控制 - 先测试基本功能
        const intensity = Math.min(average / 50, 1.0); // 降低阈值，更容易触发
        
        if (currentVrm.expressionManager) {
            if (intensity > 0.05) { // 降低触发阈值
                // 简单的 aa 口型测试
                const mouthOpen = intensity * 0.8;
                currentVrm.expressionManager.setValue('aa', mouthOpen);
                
                if (frameCount % 30 === 0) {
                    console.log('Setting mouth animation:', { intensity, mouthOpen });
                }
            } else {
                // 静音时重置口型
                currentVrm.expressionManager.setValue('aa', 0);
            }
        } else {
            console.error('No expression manager found');
        }
        
        lipSyncAnimationId = requestAnimationFrame(animateMouth);
    }
    
    console.log('Starting mouth animation loop');
    animateMouth();
}

// 在 Electron 环境中添加 WebSocket 控制按钮
if (isElectron) {
    // 在现有的控制面板创建代码中添加 WebSocket 状态按钮
    setTimeout(() => {
        const controlPanel = document.getElementById('control-panel');
        if (controlPanel) {
            // WebSocket 状态按钮
            const wsStatusButton = document.createElement('div');
            wsStatusButton.id = 'ws-status-handle';
            wsStatusButton.innerHTML = '<i class="fas fa-wifi"></i>';
            wsStatusButton.style.cssText = `
                width: 36px;
                height: 36px;
                background: rgba(255,255,255,0.95);
                border: 2px solid rgba(0,0,0,0.1);
                border-radius: 50%;
                color: #333;
                cursor: pointer;
                -webkit-app-region: no-drag;
                display: flex;
                align-items: center;
                justify-content: center;
                font-size: 14px;
                box-shadow: 0 4px 12px rgba(0,0,0,0.15);
                transition: all 0.2s ease;
                user-select: none;
                pointer-events: auto;
                backdrop-filter: blur(10px);
                color: ${wsConnected ? '#28a745' : '#dc3545'};
            `;
            // WebSocket 状态按钮事件
            wsStatusButton.addEventListener('click', (e) => {
                e.preventDefault();
                e.stopPropagation();
                if (wsConnected) {
                    // 断开连接
                    if (ttsWebSocket) {
                        ttsWebSocket.close();
                    }
                } else {
                    // 重新连接
                    initTTSWebSocket();
                }
            });
            // 添加悬停效果 - 刷新按钮
            wsStatusButton.addEventListener('mouseenter', () => {
                wsStatusButton.style.background = 'rgba(255,255,255,1)';
                wsStatusButton.style.transform = 'scale(1.1)';
                wsStatusButton.style.boxShadow = '0 6px 16px rgba(0,0,0,0.2)';
            });
            
            wsStatusButton.addEventListener('mouseleave', () => {
                wsStatusButton.style.background = 'rgba(255,255,255,0.95)';
                wsStatusButton.style.transform = 'scale(1)';
                wsStatusButton.style.boxShadow = '0 4px 12px rgba(0,0,0,0.15)';
            });
            // 更新 WebSocket 状态显示
            async function updateWSStatus() {
                wsStatusButton.style.color = wsConnected ? '#28a745' : '#dc3545';
                wsStatusButton.title = wsConnected ? await t('WebSocketConnected') :await t('WebSocketDisconnected');
            }

            // 定期更新状态
            setInterval(updateWSStatus, 1000);
            
            // 添加到控制面板（在拖拽按钮后面）
            const dragButton = controlPanel.querySelector('#drag-handle');
            if (dragButton) {
                controlPanel.insertBefore(wsStatusButton, dragButton.nextSibling);
            } else {
                controlPanel.appendChild(wsStatusButton);
            }
        }
    }, 1200);
}

// 在页面加载完成后初始化 WebSocket
document.addEventListener('DOMContentLoaded', () => {
    // 延迟初始化，确保其他组件已经准备好
    setTimeout(() => {
        initTTSWebSocket();
    }, 2000);
});
if (isElectron) {
  // 禁用 Chromium 的自动播放限制
  const disableAutoplayPolicy = () => {
    if (window.chrome && chrome.webview) {
      chrome.webview.setAutoplayPolicy('no-user-gesture-required');
    }
  };
  
  // 在用户交互后执行
  document.addEventListener('click', () => {
    disableAutoplayPolicy();
    if (currentAudioContext) {
      currentAudioContext.resume();
    }
  });
}

// 在全局变量区域添加模型切换相关变量
let currentModelIndex = 0;
let allModels = [];
let modelsInitialized = false;

// 获取所有可用模型的函数（只执行一次）
async function getAllModels() {
    if (modelsInitialized) {
        return allModels;
    }
    
    const vrmConfig = await fetchVRMConfig();
    const defaultModels = vrmConfig.defaultModels || [];
    const userModels = vrmConfig.userModels || [];
    allModels = [...defaultModels, ...userModels];
    
    // 找到当前选中模型的索引
    const selectedModelId = vrmConfig.selectedModelId;
    currentModelIndex = Math.max(0, allModels.findIndex(model => model.id === selectedModelId));
    
    modelsInitialized = true;
    console.log(`Models initialized: ${allModels.length} models available, current index: ${currentModelIndex}`);
    
    return allModels;
}

// 切换到指定索引的模型（纯前端切换）
async function switchToModel(index) {
    if (!modelsInitialized) {
        await getAllModels();
    }
    
    if (allModels.length === 0) {
        console.error('No models available');
        return;
    }
    
    // 确保索引在有效范围内（循环切换）
    const newIndex = ((index % allModels.length) + allModels.length) % allModels.length;
    
    // 如果是同一个模型，不需要切换
    if (newIndex === currentModelIndex) {
        console.log('Same model selected, no need to switch');
        return;
    }
    
    currentModelIndex = newIndex;
    const selectedModel = allModels[currentModelIndex];
    
    console.log(`Switching to model: ${selectedModel.name} (${selectedModel.id}) - Index: ${currentModelIndex}`);
    
    try {
        // 显示加载提示（可选）
        showModelSwitchingIndicator(selectedModel.name);
        
        // 移除当前VRM模型
        if (currentVrm) {
            scene.remove(currentVrm.scene);
            currentVrm = undefined;
        }
        
        // 加载新模型
        const modelPath = selectedModel.path;
        
        loader.load(
            modelPath,
            (gltf) => {
                const vrm = gltf.userData.vrm;
                
                // 优化性能
                VRMUtils.removeUnnecessaryVertices(gltf.scene);
                VRMUtils.combineSkeletons(gltf.scene);
                VRMUtils.combineMorphs(vrm);
                
                // 启用 Spring Bone 物理模拟
                if (vrm.springBoneManager) {
                    console.log('Spring Bone Manager found:', vrm.springBoneManager);
                }
                
                // 禁用视锥体剔除
                vrm.scene.traverse((obj) => {
                    obj.frustumCulled = false;
                });
                
                // 替换lookAt为扩展版本
                if (vrm.lookAt) {
                    const smoothLookAt = new VRMSmoothLookAt(vrm.humanoid, vrm.lookAt.applier);
                    smoothLookAt.copy(vrm.lookAt);
                    vrm.lookAt = smoothLookAt;
                    vrm.lookAt.target = camera;
                }
                
                currentVrm = vrm;
                console.log('New VRM loaded:', vrm);
                scene.add(vrm.scene);
                
                // 设置自然姿势
                setNaturalPose(vrm);
                
                // 隐藏加载提示
                hideModelSwitchingIndicator();
                
                console.log(`Successfully switched to model: ${selectedModel.name}`);
            },
            (progress) => {
                console.log('Loading model...', 100.0 * (progress.loaded / progress.total), '%');
                // 可以在这里更新加载进度
                updateModelLoadingProgress(progress.loaded / progress.total);
            },
            (error) => {
                console.error('Error loading model:', error);
                hideModelSwitchingIndicator();
                
                // 如果加载失败，尝试回到之前的模型
                if (allModels.length > 1) {
                    console.log('Attempting to load fallback model...');
                    // 尝试加载第一个模型作为备用
                    if (currentModelIndex !== 0) {
                        switchToModel(0);
                    }
                }
            }
        );
        
    } catch (error) {
        console.error('Error switching model:', error);
        hideModelSwitchingIndicator();
    }
}

// 显示模型切换指示器（可选功能）
function showModelSwitchingIndicator(modelName) {
    // 创建或显示加载提示
    let indicator = document.getElementById('model-switching-indicator');
    if (!indicator) {
        indicator = document.createElement('div');
        indicator.id = 'model-switching-indicator';
        indicator.style.cssText = `
            position: fixed;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            background: rgba(0, 0, 0, 0.8);
            color: white;
            padding: 20px;
            border-radius: 10px;
            font-size: 16px;
            z-index: 10000;
            text-align: center;
            backdrop-filter: blur(10px);
            transition: opacity 0.3s ease;
        `;
        document.body.appendChild(indicator);
    }
    
    indicator.innerHTML = `
        <div style="margin-bottom: 10px;">
            <i class="fas fa-sync-alt fa-spin"></i>
        </div>
        <div>Loading ${modelName}...</div>
        <div id="loading-progress" style="margin-top: 10px; font-size: 14px; opacity: 0.8;"></div>
    `;
    indicator.style.display = 'block';
    indicator.style.opacity = '1';
}

// 更新加载进度
function updateModelLoadingProgress(progress) {
    const progressElement = document.getElementById('loading-progress');
    if (progressElement) {
        progressElement.textContent = `${Math.round(progress * 100)}%`;
    }
}

// 隐藏模型切换指示器
function hideModelSwitchingIndicator() {
    const indicator = document.getElementById('model-switching-indicator');
    if (indicator) {
        indicator.style.opacity = '0';
        setTimeout(() => {
            indicator.style.display = 'none';
        }, 300);
    }
}

// 获取当前模型信息
function getCurrentModelInfo() {
    if (allModels.length > 0 && currentModelIndex >= 0 && currentModelIndex < allModels.length) {
        return allModels[currentModelIndex];
    }
    return null;
}

// 获取下一个模型信息（用于预览）
function getNextModelInfo() {
    if (allModels.length === 0) return null;
    const nextIndex = ((currentModelIndex + 1) % allModels.length + allModels.length) % allModels.length;
    return allModels[nextIndex];
}

// 获取上一个模型信息（用于预览）
function getPrevModelInfo() {
    if (allModels.length === 0) return null;
    const prevIndex = ((currentModelIndex - 1) % allModels.length + allModels.length) % allModels.length;
    return allModels[prevIndex];
}

// 在 Electron 环境中添加模型切换按钮
if (isElectron) {
    setTimeout(async () => {
        const controlPanel = document.getElementById('control-panel');
        if (controlPanel) {
            // 获取所有模型（只执行一次）
            await getAllModels();
            
            // 向上箭头按钮（切换到上一个模型）
            const prevModelButton = document.createElement('div');
            prevModelButton.id = 'prev-model-handle';
            prevModelButton.innerHTML = '<i class="fas fa-chevron-up"></i>';
            prevModelButton.style.cssText = `
                width: 36px;
                height: 36px;
                background: rgba(255,255,255,0.95);
                border: 2px solid rgba(0,0,0,0.1);
                border-radius: 50%;
                color: #333;
                cursor: pointer;
                -webkit-app-region: no-drag;
                display: flex;
                align-items: center;
                justify-content: center;
                font-size: 14px;
                box-shadow: 0 4px 12px rgba(0,0,0,0.15);
                transition: all 0.2s ease;
                user-select: none;
                pointer-events: auto;
                backdrop-filter: blur(10px);
            `;
            
            // 向下箭头按钮（切换到下一个模型）
            const nextModelButton = document.createElement('div');
            nextModelButton.id = 'next-model-handle';
            nextModelButton.innerHTML = '<i class="fas fa-chevron-down"></i>';
            nextModelButton.style.cssText = `
                width: 36px;
                height: 36px;
                background: rgba(255,255,255,0.95);
                border: 2px solid rgba(0,0,0,0.1);
                border-radius: 50%;
                color: #333;
                cursor: pointer;
                -webkit-app-region: no-drag;
                display: flex;
                align-items: center;
                justify-content: center;
                font-size: 14px;
                box-shadow: 0 4px 12px rgba(0,0,0,0.15);
                transition: all 0.2s ease;
                user-select: none;
                pointer-events: auto;
                backdrop-filter: blur(10px);
            `;
            
            // 添加悬停效果和工具提示 - 上一个模型按钮
            prevModelButton.addEventListener('mouseenter', async () => {
                prevModelButton.style.background = 'rgba(255,255,255,1)';
                prevModelButton.style.transform = 'scale(1.1)';
                prevModelButton.style.boxShadow = '0 6px 16px rgba(0,0,0,0.2)';
                
                // 显示下一个模型的名称
                const prevModel = getPrevModelInfo();
                if (prevModel) {
                    prevModelButton.title = `${await t('Previous')}: ${prevModel.name}`;
                }
            });
            
            prevModelButton.addEventListener('mouseleave', () => {
                prevModelButton.style.background = 'rgba(255,255,255,0.95)';
                prevModelButton.style.transform = 'scale(1)';
                prevModelButton.style.boxShadow = '0 4px 12px rgba(0,0,0,0.15)';
            });
            
            // 添加悬停效果和工具提示 - 下一个模型按钮
            nextModelButton.addEventListener('mouseenter', async () => {
                nextModelButton.style.background = 'rgba(255,255,255,1)';
                nextModelButton.style.transform = 'scale(1.1)';
                nextModelButton.style.boxShadow = '0 6px 16px rgba(0,0,0,0.2)';
                
                // 显示下一个模型的名称
                const nextModel = getNextModelInfo();
                if (nextModel) {
                    nextModelButton.title = `${await t('Next')}: ${nextModel.name}`;
                }
            });
            
            nextModelButton.addEventListener('mouseleave', () => {
                nextModelButton.style.background = 'rgba(255,255,255,0.95)';
                nextModelButton.style.transform = 'scale(1)';
                nextModelButton.style.boxShadow = '0 4px 12px rgba(0,0,0,0.15)';
            });
            
            // 上一个模型按钮点击事件
            prevModelButton.addEventListener('click', (e) => {
                e.preventDefault();
                e.stopPropagation();
                if (allModels.length > 1) {
                    switchToModel(currentModelIndex - 1);
                }
            });
            
            // 下一个模型按钮点击事件
            nextModelButton.addEventListener('click', (e) => {
                e.preventDefault();
                e.stopPropagation();
                if (allModels.length > 1) {
                    switchToModel(currentModelIndex + 1);
                }
            });
            
            // 设置按钮初始状态
            async function initModelButtons() {
                if (allModels.length <= 1) {
                    // 如果只有一个或没有模型，禁用按钮
                    prevModelButton.style.opacity = '0.5';
                    prevModelButton.style.cursor = 'not-allowed';
                    prevModelButton.title = 'No other models available';
                    
                    nextModelButton.style.opacity = '0.5';
                    nextModelButton.style.cursor = 'not-allowed';
                    nextModelButton.title = 'No other models available';
                } else {
                    // 设置初始工具提示
                    const prevModel = getPrevModelInfo();
                    const nextModel = getNextModelInfo();
                    
                    prevModelButton.title = prevModel ? `Previous: ${prevModel.name}` : 'Previous Model';
                    nextModelButton.title = nextModel ? `Next: ${nextModel.name}` : 'Next Model';
                }
                
                console.log(`Model buttons initialized. Current: ${getCurrentModelInfo()?.name || 'Unknown'} (${currentModelIndex + 1}/${allModels.length})`);
            }
            
            initModelButtons();
            
            // 添加到控制面板
            const wsStatusButton = controlPanel.querySelector('#ws-status-handle');
            const dragButton = controlPanel.querySelector('#drag-handle');
            
            if (wsStatusButton) {
                controlPanel.insertBefore(nextModelButton, wsStatusButton.nextSibling);
                controlPanel.insertBefore(prevModelButton, nextModelButton);
            } else if (dragButton) {
                controlPanel.insertBefore(nextModelButton, dragButton.nextSibling);
                controlPanel.insertBefore(prevModelButton, nextModelButton);
            } else {
                controlPanel.appendChild(prevModelButton);
                controlPanel.appendChild(nextModelButton);
            }
            
            console.log(`Model switching buttons added. Available models: ${allModels.length}`);
        }
    }, 1300);
}

animate();