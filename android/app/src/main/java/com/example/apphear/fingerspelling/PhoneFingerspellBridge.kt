package com.example.apphear.fingerspelling

import androidx.camera.core.ImageProxy
import com.example.apphear.perceptionvnext.PhoneRawObservation

internal fun PhoneRawObservation.fingerspellObservation() = CommonObservation(
    timestampMs, sourceWidth, sourceHeight, handXy, handJointValid, handProposalSupport,
    handPresence, handObserved, handProposalPresent, handRoiCenterSide,
    bodyXy, bodySupport, bodyValid, bodyAvailable,
)

/** Borrows CameraX RGBA only inside analyze(); never retains ImageProxy or mirrors pixels. */
internal class PhoneRgbSource(image: ImageProxy): RgbSource by UprightRgbaSource(
    image.width,image.height,image.planes[0].rowStride,image.planes[0].pixelStride,
    image.imageInfo.rotationDegrees,image.planes[0].buffer,
)
