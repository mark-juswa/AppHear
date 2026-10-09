package com.example.apphear.perceptionvnext

/** Lossless raw-v1 to Recognition V2 adapter shared by validation and the real app. */
internal fun phoneRecognitionRawSequence(observations: List<PhoneRawObservation>): RecognitionV2.RawSequence {
    require(observations.isNotEmpty())
    val t = observations.size
    return RecognitionV2.RawSequence(
        schema = RecognitionV2.RAW_SCHEMA,
        imageSemantics = "UPRIGHT_UNMIRRORED_SOURCE_RGB",
        frameIndex = IntArray(t) { observations[it].sourceIndex },
        timestampMs = DoubleArray(t) { observations[it].timestampMs },
        sourceSize = IntArray(t * 2).also { target ->
            observations.forEachIndexed { index, item ->
                target[index * 2] = item.sourceWidth
                target[index * 2 + 1] = item.sourceHeight
            }
        },
        handXy = FloatArray(t * 2 * 21 * 2).also { target ->
            observations.forEachIndexed { frame, item ->
                for (side in 0..1) item.handXy[side].copyInto(target, (frame * 2 + side) * 42)
            }
        },
        handProposalSupport = FloatArray(t * 2 * 21).also { target ->
            observations.forEachIndexed { frame, item ->
                for (side in 0..1) item.handProposalSupport[side].copyInto(target, (frame * 2 + side) * 21)
            }
        },
        handJointValid = BooleanArray(t * 2 * 21).also { target ->
            observations.forEachIndexed { frame, item ->
                for (side in 0..1) item.handJointValid[side].copyInto(target, (frame * 2 + side) * 21)
            }
        },
        handPresence = FloatArray(t * 2).also { target ->
            observations.forEachIndexed { frame, item -> item.handPresence.copyInto(target, frame * 2) }
        },
        handObserved = BooleanArray(t * 2).also { target ->
            observations.forEachIndexed { frame, item -> item.handObserved.copyInto(target, frame * 2) }
        },
        bodyXy = FloatArray(t * 16).also { target ->
            observations.forEachIndexed { frame, item -> item.bodyXy.copyInto(target, frame * 16) }
        },
        bodySupport = FloatArray(t * 8).also { target ->
            observations.forEachIndexed { frame, item -> item.bodySupport.copyInto(target, frame * 8) }
        },
        bodyValid = BooleanArray(t * 8).also { target ->
            observations.forEachIndexed { frame, item -> item.bodyValid.copyInto(target, frame * 8) }
        },
        bodyAvailable = BooleanArray(t) { observations[it].bodyAvailable },
    ).also { it.validate() }
}
