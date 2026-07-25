package com.example.aslrecorder.model;

import java.io.Serializable;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

public class SessionSummary implements Serializable {

    public String signLabel;
    public String signerId;
    public String sessionId;
    public int    targetCount;
    public int    acceptedCount;
    public int    rejectedCount;
    public int    totalAttempts;
    public String folderPath;
    public String recordingDate;

    // rejection code -> count
    public Map<String, Integer> rejectionCounts = new HashMap<>();

    // Filenames of rejected samples that still need a redo
    public List<String> redoFilenames = new ArrayList<>();

    public SessionSummary() {}

    public void recordRejection(String rejectionCode) {
        rejectedCount++;
        totalAttempts++;
        int current = rejectionCounts.containsKey(rejectionCode)
                ? rejectionCounts.get(rejectionCode) : 0;
        rejectionCounts.put(rejectionCode, current + 1);
    }

    public void recordAcceptance() {
        acceptedCount++;
        totalAttempts++;
    }

    public boolean isComplete() {
        return acceptedCount >= targetCount;
    }

    public int remaining() {
        return Math.max(0, targetCount - acceptedCount);
    }

    public int redoNeeded() {
        return redoFilenames.size();
    }
}
