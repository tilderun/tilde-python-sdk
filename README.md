# loobooktilde — AI Training Pipeline

Runs FLUX.1-dev LoRA training on RunPod and stores checkpoints in Tilde.

```
S3 (training images)
    → RunPod (ai-toolkit, RTX PRO 6000 Blackwell)
        → Tilde (versioned checkpoints)
```

## Prerequisites

- AWS credentials with access to the `bernardjames` S3 bucket
- RunPod API key with secrets configured (see below)
- Tilde API key
- HuggingFace account with access to `black-forest-labs/FLUX.1-dev`

### RunPod secrets (set once in RunPod console)

| Secret name            | Value                        |
|------------------------|------------------------------|
| `TILDE_API_KEY`        | Your Tilde API key           |
| `HF_TOKEN`             | HuggingFace token            |
| `AWS_ACCESS_KEY_ID`    | AWS access key               |
| `AWS_SECRET_ACCESS_KEY`| AWS secret key               |
| `AWS_DEFAULT_REGION`   | e.g. `us-east-2`             |

### `.env` (local, never commit)

```
TILDE_API_KEY=tak-...
RUNPOD_API_KEY=rpa_...
```

## Running a training job

1. Upload training images and `.txt` captions to S3:
   ```bash
   aws s3 cp ./my-images/ s3://bernardjames/training/my-run-001/ --recursive
   ```

2. Launch training:
   ```bash
   bash train.sh my-run-001          # 2000 steps (production)
   bash train.sh my-run-001 200      # 200 steps (quick test)
   ```

3. Monitor in RunPod console:
   - **TensorBoard** → Connect → port 6006
   - **ostris UI** → Connect → port 8675

4. Checkpoints are committed to Tilde automatically when training completes:
   ```
   checkpoints/<run-id>/model_step-XXXX.safetensors
   ```

## Exporting a checkpoint to S3

After reviewing checkpoints in Tilde:
```bash
bash export_to_s3.sh \
  --run-id     my-run-001 \
  --step       1000 \
  --s3-out     s3://bernardjames/models/my-run-001/
```

## Key training parameters

Pass via environment variables or extend `train.sh`:

| Variable          | Default                        | Description              |
|-------------------|--------------------------------|--------------------------|
| `MODEL_NAME`      | `black-forest-labs/FLUX.1-dev` | Base model               |
| `TRAINING_STEPS`  | `2000`                         | Total training steps     |
| `SAVE_EVERY`      | `250`                          | Checkpoint frequency     |
| `LR`              | `1e-4`                         | Learning rate            |
| `LORA_RANK`       | `16`                           | LoRA rank                |
| `TRIGGER_WORD`    | _(none)_                       | Subject trigger word     |

## Repo layout

```
train.sh                  # Entry point — run this
run_pipeline.sh           # Full pipeline orchestration
train_script/
  startup.sh              # Pod startup (uploaded to S3, runs on RunPod)
  entrypoint.py           # Training logic (uploaded to S3, runs on RunPod)
sandbox/
  coordinator.py          # Tilde sandbox — creates RunPod pod, polls, writes manifest
.pipeline_config.json     # Tilde org/repo and S3 bucket
export_to_s3.sh           # Export approved checkpoints from Tilde → S3
```

## How it works

1. `train.sh` calls `run_pipeline.sh`
2. `run_pipeline.sh` uploads `startup.sh` + `entrypoint.py` to S3, then launches the **coordinator** inside a Tilde sandbox
3. The coordinator creates a RunPod GPU pod with all secrets injected, polls until it exits
4. The pod runs `startup.sh` which: installs deps, starts the ostris UI + TensorBoard, then runs `entrypoint.py`
5. `entrypoint.py` downloads training images from S3, generates a FLUX LoRA config, runs `ai-toolkit`, and commits checkpoints to Tilde on completion
6. The coordinator writes a run manifest to `/sandbox/runs/<run-id>/manifest.json`
