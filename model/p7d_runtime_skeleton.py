"""P7-D random graph/export gate. No training or dataset access entrypoint."""
from __future__ import annotations

import contextlib
import hashlib
import io
import json
import os
from pathlib import Path

os.environ.setdefault("CUDA_VISIBLE_DEVICES", "-1")
import numpy as np
import tensorflow as tf
from tensorflow.lite.python import schema_py_generated as schema

ROOT = Path(__file__).resolve().parents[1]
PARENT = ROOT / "artifacts/recognition_upgrade/p7c_mobile_architecture_selection_01"
OUT = ROOT / "artifacts/recognition_upgrade/p7d_android_runtime_skeleton_feasibility_01"


def save(name: str, value: object) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / name).write_text(json.dumps(value, indent=2, allow_nan=False), encoding="utf-8")


def run() -> None:
    if (OUT / "random_skeleton.tflite").exists():
        raise RuntimeError("P7D refuses to overwrite an existing exported graph")
    for row in json.loads((PARENT / "artifact_hash_manifest.json").read_text())["artifacts"]:
        assert hashlib.sha256((PARENT / row["path"]).read_bytes()).hexdigest() == row["sha256"]
    tf.keras.utils.set_random_seed(707)
    ledger = json.loads((PARENT / "p7c_theoretical_compute_report.json").read_text())["operations"]
    cfg = {r["name"]: r for r in ledger}
    ordinals = {r["name"]: i for i, r in enumerate(ledger)}
    stages = json.loads((PARENT / "p7c_selected_architecture.json").read_text())["feature_stages"]
    save("p7d_graph_identity.json", {"architecture": "FA_DS_SPATIAL_V1", "seed": 707,
         "ordinal_convention": "Zero-based convolution ordinal in frozen P7C analytical operations ledger",
         "initializers": [{"name": n, "HeNormal_seed": 707+i} for n, i in ordinals.items()],
         "training": False, "policy": "POLICY_UNCONFIGURED"})
    layers: dict = {}
    norms: dict = {}

    def layer(x: object, name: str, stride: int = 1) -> object:
        r = cfg[name]
        init = tf.keras.initializers.HeNormal(seed=707 + ordinals[name])
        args = dict(kernel_size=r["kernel"], strides=stride, padding="same", use_bias=not r["batch_norm"], name=name)
        if r["kind"] == "DW":
            conv = tf.keras.layers.DepthwiseConv2D(depthwise_initializer=init, **args)
        else:
            conv = tf.keras.layers.Conv2D(r["output_shape"][-1], kernel_initializer=init, **args)
        layers[name] = conv
        x = conv(x)
        assert list(x.shape) == r["output_shape"], (name, x.shape)
        if r["batch_norm"]:
            bn = tf.keras.layers.BatchNormalization(axis=-1, epsilon=.001, momentum=.99, name=name+"_bn")
            norms[name] = bn
            x = bn(x, training=False)
            x = tf.keras.layers.ReLU(max_value=6, name=name+"_relu6")(x)
        return x

    def graph(x: object, apply: object, resize: object, concat: object, mean: object) -> dict:
        x = apply(x, "stem", 2)
        features = {}
        for block in stages:
            n = block["name"]
            x = apply(x, n+"_dw", block["stride"])
            x = apply(x, n+"_pw")
            features[n] = x
        c4 = x
        p2 = apply(features["C2_2"], "lateral_C2")
        p3 = resize(apply(features["C3_3"], "lateral_C3"))
        p4 = resize(apply(c4, "lateral_C4"))
        x = concat([p2, p3, p4])
        for n in ("neck1", "neck2"):
            x = apply(apply(x, n+"_dw"), n+"_pw")
        return {"heatmap_logits": apply(x, "heatmap_logits"), "identity_logits": apply(mean(c4), "identity_logits")}

    inp = tf.keras.Input(batch_shape=(1,384,384,3), dtype="float32", name="rgb")
    outputs = graph(inp, layer, lambda x: tf.keras.layers.Resizing(96,96,interpolation="bilinear")(x),
                    lambda x: tf.keras.layers.Concatenate(axis=-1)(x),
                    lambda x: tf.keras.layers.GlobalAveragePooling2D(keepdims=True)(x))
    model = tf.keras.Model(inp, outputs, name="FA_DS_SPATIAL_V1")
    trainable = sum(int(np.prod(v.shape)) for v in model.trainable_weights)
    assert trainable == 154076
    assert len(layers) == 40 and len(norms) == 38 and len(model.layers) == 121
    folded: dict = {}
    for name, conv in layers.items():
        w = conv.get_weights()[0]
        if name in norms:
            gamma, beta, mu, var = norms[name].get_weights()
            factor = gamma / np.sqrt(var + np.float32(.001))
            w = w * factor.reshape((1,1,-1,1) if cfg[name]["kind"] == "DW" else (1,1,1,-1))
            b = beta - mu * factor
        else:
            b = conv.get_weights()[1]
        folded[name] = (tf.constant(w), tf.constant(b))
    folded_count = sum(int(np.prod(v.shape)) for pair in folded.values() for v in pair)
    assert folded_count == 151292

    def apply_folded(x: tf.Tensor, name: str, stride: int = 1) -> tf.Tensor:
        w, b = folded[name]
        if cfg[name]["kind"] == "DW":
            x = tf.nn.depthwise_conv2d(x, w, strides=[1,stride,stride,1], padding="SAME")
        else:
            x = tf.nn.conv2d(x, w, strides=[1,stride,stride,1], padding="SAME")
        x = tf.nn.bias_add(x,b)
        return tf.nn.relu6(x) if cfg[name]["batch_norm"] else x

    @tf.function(input_signature=[tf.TensorSpec([1,384,384,3], tf.float32, name="rgb")])
    def serve(rgb: tf.Tensor) -> dict:
        return graph(rgb, apply_folded,
                     lambda x: tf.raw_ops.ResizeBilinear(images=x,size=[96,96],align_corners=False,half_pixel_centers=True),
                     lambda x: tf.concat(x,axis=-1), lambda x: tf.reduce_mean(x,axis=[1,2],keepdims=True))

    synthetic = np.random.default_rng(707).uniform(-1,1,(1,384,384,3)).astype(np.float32)
    expected = model(synthetic, training=False)
    actual = serve(synthetic)
    parity = {n: float(np.max(np.abs(expected[n].numpy()-actual[n].numpy()))) for n in actual}
    for n in actual:
        np.testing.assert_allclose(expected[n], actual[n], atol=1e-4, rtol=1e-4)
    macs = sum(int(np.prod(l.output.shape[1:3])) * int(np.prod(l.get_weights()[0].shape)) for l in layers.values())
    assert macs == 219110656
    save("p7d_graph_structure_audit.json", {"passed": True, "keras_layers": len(model.layers), "convolutions":len(layers),
         "BN_layers":len(norms), "trainable_parameters":trainable, "folded_inference_parameters":folded_count,
         "MACs":macs, "bn_fold_synthetic_max_abs":parity,
         "layers":[{"name":l.name,"class":type(l).__name__,"shape":list(l.output.shape)} for l in model.layers]})
    converter = tf.lite.TFLiteConverter.from_concrete_functions([serve.get_concrete_function()])
    converter.target_spec.supported_ops = [tf.lite.OpsSet.TFLITE_BUILTINS]
    converter.optimizations = []
    converter.allow_custom_ops = False
    blob = converter.convert()
    (OUT / "random_skeleton.tflite").write_bytes(blob)
    assert blob[4:8] == b"TFL3"
    fb = schema.Model.GetRootAsModel(blob,0)
    names = {v:k for k,v in vars(schema.BuiltinOperator).items() if isinstance(v,int)}
    limits = {"CONV_2D":8,"DEPTHWISE_CONV_2D":7,"RELU6":3,"RESIZE_BILINEAR":4,"CONCATENATION":4,"MEAN":3}
    ops=[]
    for i in range(fb.OperatorCodesLength()):
        op=fb.OperatorCodes(i); name=names[op.BuiltinCode()]
        ops.append({"name":name,"version":op.Version(),"runtime_max_version":limits.get(name),
                    "supported":name in limits and op.Version()<=limits[name],"custom":op.CustomCode() is not None})
    compatible=all(r["supported"] and not r["custom"] for r in ops)
    interpreter=tf.lite.Interpreter(model_content=blob,num_threads=2)
    interpreter.allocate_tensors()
    inputs=interpreter.get_input_details(); outs=interpreter.get_output_details()
    assert inputs[0]["shape"].tolist()==[1,384,384,3] and inputs[0]["dtype"]==np.float32
    bindings={}
    for index,t in enumerate(outs):
        shape=t["shape"].tolist()
        name="heatmap_logits" if shape==[1,96,96,50] else "identity_logits" if shape==[1,1,1,2] else None
        assert name is not None and t["dtype"]==np.float32 and name not in bindings
        bindings[name]={"output_index":index,"tensor_index":int(t["index"]),"tensor_name":t["name"],"shape":shape}
    assert len(bindings)==2
    interpreter.set_tensor(inputs[0]["index"],synthetic);interpreter.invoke()
    lite_parity={}
    for n,b in bindings.items():
        value=interpreter.get_tensor(b["tensor_index"])
        np.testing.assert_allclose(value,actual[n],atol=1e-4,rtol=1e-4)
        lite_parity[n]=float(np.max(np.abs(value-actual[n].numpy())))
    capture=io.StringIO()
    with contextlib.redirect_stdout(capture):
        tf.lite.experimental.Analyzer.analyze(model_content=blob)
    (OUT / "tflite_analyzer.txt").write_text(capture.getvalue(),encoding="utf-8")
    save("p7d_tflite_operator_audit.json",{"passed":compatible,"operators":ops,"schema_version":fb.Version(),
         "builtin_only":all(not o["custom"] for o in ops),"runtime":"2.16.1",
         "source":"https://raw.githubusercontent.com/tensorflow/tensorflow/v2.16.1/tensorflow/lite/core/kernels/register.cc",
         "bindings":bindings,"synthetic_TF_TFLite_max_abs":lite_parity,"device_load":"NOT_YET_RUN"})
    save("p7d_model_identity.json",{"sha256":hashlib.sha256(blob).hexdigest(),"bytes":len(blob),"bindings":bindings,
         "schema_id":"APPHEAR_FAMILY_A_FRAME_V1","policy":"POLICY_UNCONFIGURED","architecture":"FA_DS_SPATIAL_V1"})
    save("p7d_export_contract.json",{"tensorflow":tf.__version__,"keras":tf.keras.__version__,"precision":"FP32",
         "optimizations":[],"representative_dataset":False,"training":False,"builtin_only":True,"passed":compatible})
    print(json.dumps({"graph_pass":True,"export_pass":compatible,"bytes":len(blob),"operators":ops}))
    if not compatible:
        raise RuntimeError("P7D_EXPORT_RUNTIME_COMPATIBILITY_BLOCKED")


if __name__ == "__main__":
    run()
