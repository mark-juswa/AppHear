"""Guarded P5-B single-seed TCN training and evaluation."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
from pathlib import Path
from typing import Any

os.environ.setdefault("TF_ENABLE_ONEDNN_OPTS", "0")
import numpy as np  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "artifacts/recognition_upgrade/p5_representation_v2/p5b_baseline_01"
DATA = ROOT / "artifacts/recognition_upgrade/p5_representation_v2/p5b_migration_01/dataset"
CONTRACT = ROOT / "artifacts/recognition_upgrade/p5_representation_v2/p5b_preparation_01/p5b_training_contract.json"
EXPECTED_COUNTS = {"train":3926,"val":816,"test":2620}
EXPECTED_SHAPE = (96,238)


def sha256(path: Path) -> str:
    h=hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda:f.read(1024*1024),b""): h.update(chunk)
    return h.hexdigest()


def load_split(name: str) -> tuple[np.ndarray,...]:
    path=DATA/f"{name}.npz"
    if not path.is_file(): raise RuntimeError(f"missing migration split: {path}")
    with np.load(path,allow_pickle=False) as z:
        result=(np.asarray(z["X"],np.float32),np.asarray(z["y"],np.int32),np.asarray(z["frame_mask"],bool),np.asarray(z["sample_ids"]),np.asarray(z["signer_group_ids"]))
    if result[0].shape != (EXPECTED_COUNTS[name],*EXPECTED_SHAPE): raise RuntimeError(f"{name} shape mismatch: {result[0].shape}")
    if result[2].shape != (EXPECTED_COUNTS[name],96): raise RuntimeError(f"{name} mask mismatch")
    if not np.isfinite(result[0]).all(): raise RuntimeError(f"{name} contains NaN/Inf")
    return result


def preflight(require_test: bool=True) -> dict[str,Any]:
    if not CONTRACT.is_file(): raise RuntimeError("missing frozen training contract")
    names=("train","val","test") if require_test else ("train","val")
    loaded={name:load_split(name) for name in names}
    train_ids=set(map(str,loaded["train"][3])); val_ids=set(map(str,loaded["val"][3]))
    if train_ids & val_ids: raise RuntimeError("train/validation sample leakage")
    train_signers=set(map(str,loaded["train"][4])); val_signers=set(map(str,loaded["val"][4]))
    if train_signers & val_signers: raise RuntimeError("train/validation signer leakage")
    if require_test and ((train_ids|val_ids)&set(map(str,loaded["test"][3]))): raise RuntimeError("test sample leakage")
    if require_test:
        test_signers=set(map(str,loaded["test"][4]))
        if (train_signers|val_signers)&test_signers: raise RuntimeError("test signer leakage")
    manifest=ROOT/"artifacts/recognition_upgrade/phase1_full_vocab/manifest_01/canonical_manifest.csv"
    with manifest.open("r",encoding="utf-8-sig",newline="") as f: rows=list(csv.DictReader(f))
    by_hash={}
    for r in rows: by_hash.setdefault(r["raw_video_sha256"].upper(),set()).add(r["role"])
    for digest,roles in by_hash.items():
        if "protected_clean_replay" in roles and roles & {"primary_train","supplement_train"}: raise RuntimeError(f"protected hash in train: {digest}")
    return {"contract_sha256":sha256(CONTRACT),"counts":{k:len(v[1]) for k,v in loaded.items()},"passed":True}


def build_model(num_classes: int=236):
    import tensorflow as tf
    from model.model import build_streaming_classifier
    model=build_streaming_classifier(96,238,num_classes,blocks=4,channels=64,dilations=(1,2,4,8),kernel=3,dropout=0.3)
    model.compile(optimizer=tf.keras.optimizers.AdamW(5e-4,weight_decay=1e-4),loss=tf.keras.losses.SparseCategoricalCrossentropy(),weighted_metrics=[tf.keras.metrics.SparseCategoricalAccuracy(name="pf_acc")])
    return model


def dataset(x,y,mask,batch,shuffle,seed):
    import tensorflow as tf
    ypf=np.repeat(y[:,None],96,axis=1)
    ds=tf.data.Dataset.from_tensor_slices((x,ypf,mask.astype(np.float32)))
    if shuffle: ds=ds.shuffle(len(x),seed=seed,reshuffle_each_iteration=True)
    return ds.batch(batch).prefetch(tf.data.AUTOTUNE)


def train(args: argparse.Namespace)->int:
    import tensorflow as tf
    preflight(False); tf.keras.utils.set_random_seed(101)
    xtr,ytr,mtr,_,_=load_split("train"); xv,yv,mv,_,_=load_split("val")
    RUN.mkdir(parents=True,exist_ok=True); hist=RUN/"history.csv"; latest=RUN/"latest.keras"; best=RUN/"best.keras"
    if args.resume:
        if not latest.is_file(): raise RuntimeError("no latest.keras to resume")
        model=tf.keras.models.load_model(latest,safe_mode=False)
        with hist.open("r",encoding="utf-8",newline="") as f: initial=max((int(r["epoch"]) for r in csv.DictReader(f)),default=-1)+1
    else:
        if any(p.exists() for p in (hist,latest,best)): raise RuntimeError("run exists; use --resume")
        model=build_model(); initial=0
    callbacks=[tf.keras.callbacks.ModelCheckpoint(best,monitor="val_pf_acc",mode="max",save_best_only=True),tf.keras.callbacks.ModelCheckpoint(latest),tf.keras.callbacks.CSVLogger(hist,append=args.resume),tf.keras.callbacks.EarlyStopping(monitor="val_pf_acc",mode="max",patience=8,restore_best_weights=True)]
    model.fit(dataset(xtr,ytr,mtr,32,True,101),validation_data=dataset(xv,yv,mv,32,False,101),initial_epoch=initial,epochs=40,callbacks=callbacks,verbose=2,shuffle=False)
    model.save(RUN/"final.keras"); return 0


def smoke(_: argparse.Namespace)->int:
    import tensorflow as tf
    tf.keras.utils.set_random_seed(101); model=build_model(12)
    rng=np.random.default_rng(101); x=rng.normal(size=(6,96,238)).astype(np.float32); y=np.arange(6,dtype=np.int32)%12; m=np.ones((6,96),bool)
    result=model.train_on_batch(x,np.repeat(y[:,None],96,axis=1),sample_weight=m.astype(np.float32),return_dict=True)
    RUN.mkdir(parents=True,exist_ok=True); (RUN/"smoke.json").write_text(json.dumps({"input_shape":list(x.shape),"output_shape":list(model(x[:1],training=False).shape),"parameter_count":model.count_params(),"train_on_batch":{k:float(v) for k,v in result.items()},"passed":True},indent=2)+"\n",encoding="utf-8")
    print(json.dumps(json.loads((RUN/"smoke.json").read_text()),indent=2)); return 0


def clip_probs(model,x,mask):
    raw=np.asarray(model.predict(x,batch_size=32,verbose=0)); denom=np.maximum(mask.sum(1,keepdims=True),1); return (raw*mask[:,:,None]).sum(1)/denom


def missingness(x,mask):
    left=(x[:,:,236]>0.5)&mask; right=(x[:,:,237]>0.5)&mask
    def maxrun(v):
        best=cur=0
        for b in v:
            cur=cur+1 if not b else 0; best=max(best,cur)
        return best
    out=[]
    for i in range(len(x)):
        real=mask[i]; n=max(int(real.sum()),1); l=left[i][real]; r=right[i][real]
        out.append({"left_observed_fraction":float(l.sum()/n),"right_observed_fraction":float(r.sum()/n),"both_observed_fraction":float((l&r).sum()/n),"neither_observed_fraction":float((~l&~r).sum()/n),"left_max_missing_run":maxrun(l),"right_max_missing_run":maxrun(r)})
    return out


def classification_metrics(y_true: np.ndarray, y_pred: np.ndarray, num_classes: int):
    """Return sklearn-equivalent zero-division metrics without an optional dependency."""
    truth=np.asarray(y_true,dtype=np.int64); pred=np.asarray(y_pred,dtype=np.int64)
    if truth.shape != pred.shape or truth.ndim != 1: raise ValueError("classification label shape mismatch")
    if np.any(truth<0) or np.any(truth>=num_classes) or np.any(pred<0) or np.any(pred>=num_classes): raise ValueError("classification label out of range")
    matrix=np.zeros((num_classes,num_classes),dtype=np.int64); np.add.at(matrix,(truth,pred),1)
    support=matrix.sum(axis=1); predicted=matrix.sum(axis=0); tp=np.diag(matrix)
    precision=np.divide(tp,predicted,out=np.zeros(num_classes,dtype=np.float64),where=predicted>0)
    recall=np.divide(tp,support,out=np.zeros(num_classes,dtype=np.float64),where=support>0)
    f1=np.divide(2*precision*recall,precision+recall,out=np.zeros(num_classes,dtype=np.float64),where=(precision+recall)>0)
    active=(support+predicted)>0
    macro=float(np.mean(f1[active])) if np.any(active) else 0.0
    return matrix,precision,recall,f1,support,macro


def evaluate(_: argparse.Namespace)->int:
    import tensorflow as tf
    preflight(True); model=tf.keras.models.load_model(RUN/"best.keras",safe_mode=False)
    x,y,m,ids,signers=load_split("test"); probs=clip_probs(model,x,m); pred=probs.argmax(1); top5=np.argsort(probs,axis=1)[:,-5:]
    matrix,precision,recall,f1,support,macro=classification_metrics(y,pred,236)
    miss=missingness(x,m); top1=float(np.mean(pred==y)); t5=float(np.mean([y[i] in top5[i] for i in range(len(y))]))
    RUN.mkdir(parents=True,exist_ok=True)
    with (RUN/"test_predictions.csv").open("w",encoding="utf-8",newline="") as f:
        fields=["sample_id","signer_group_id","true_class","pred_class","correct",*miss[0].keys()]; w=csv.DictWriter(f,fieldnames=fields);w.writeheader()
        for i in range(len(y)): w.writerow({"sample_id":ids[i],"signer_group_id":signers[i],"true_class":int(y[i]),"pred_class":int(pred[i]),"correct":int(y[i]==pred[i]),**miss[i]})
    np.save(RUN/"confusion_matrix.npy",matrix)
    with (RUN/"per_class_metrics.csv").open("w",encoding="utf-8",newline="") as f:
        w=csv.writer(f);w.writerow(["class_id","precision","recall","f1","support"])
        for i in range(236): w.writerow([i,float(precision[i]),float(recall[i]),float(f1[i]),int(support[i])])
    test_eval=model.evaluate(dataset(x,y,m,32,False,101),verbose=0,return_dict=True)
    bins={"strong_both":"both_observed_fraction >= 0.90","moderate":"0.50 <= both_observed_fraction < 0.90","weak_both":"both_observed_fraction < 0.50"}
    stats={}
    both=np.asarray([r["both_observed_fraction"] for r in miss]); masks={"strong_both":both>=.9,"moderate":(both>=.5)&(both<.9),"weak_both":both<.5}
    for k,z in masks.items():
        stratum_macro=classification_metrics(y[z],pred[z],236)[-1] if z.any() else None
        stats[k]={"n":int(z.sum()),"top1":float(np.mean(pred[z]==y[z])) if z.any() else None,"macro_f1":stratum_macro}
    payload={"top1":top1,"top5":t5,"macro_f1":macro,"test_per_frame_loss_accuracy":{k:float(v) for k,v in test_eval.items()},"missingness_bins_frozen_before_test":bins,"strata":stats,"passed":True}
    (RUN/"evaluation_summary.json").write_text(json.dumps(payload,indent=2)+"\n",encoding="utf-8"); print(json.dumps(payload,indent=2)); return 0


def main()->int:
    p=argparse.ArgumentParser(); s=p.add_subparsers(dest="cmd",required=True)
    q=s.add_parser("smoke");q.set_defaults(func=smoke)
    q=s.add_parser("train");q.add_argument("--resume",action="store_true");q.set_defaults(func=train)
    q=s.add_parser("preflight");q.set_defaults(func=lambda _: (print(json.dumps(preflight(True),indent=2)) or 0))
    q=s.add_parser("evaluate");q.set_defaults(func=evaluate)
    a=p.parse_args();return a.func(a)
if __name__=="__main__":raise SystemExit(main())
