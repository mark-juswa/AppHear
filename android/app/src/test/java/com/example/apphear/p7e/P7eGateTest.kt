package com.example.apphear.p7e

import org.junit.Assert.*
import org.junit.Test

class P7eGateTest {
    @Test fun exactCameraBoundary(){assertTrue(P7eGate.cameraPass(900,900,60.0))}
    @Test fun noRoundingCapture(){assertFalse(P7eGate.cameraPass(899,900,60.0))}
    @Test fun noRoundingAnalyzer(){assertFalse(P7eGate.cameraPass(900,899,60.0))}
    @Test fun exactIntegratedBoundary(){assertTrue(P7eGate.integratedPass(2700,2700,2700,180.0,62.7532812))}
    @Test fun integratedNeedsCompleted(){assertFalse(P7eGate.integratedPass(2700,2700,2699,180.0,20.0))}
    @Test fun integratedNeedsLatency(){assertFalse(P7eGate.integratedPass(2700,2700,2700,180.0,62.75328121))}
    @Test fun nonfiniteRejected(){assertFalse(P7eGate.integratedPass(2700,2700,2700,180.0,Double.NaN))}
}
