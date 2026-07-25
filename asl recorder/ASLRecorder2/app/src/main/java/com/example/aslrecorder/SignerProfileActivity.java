package com.example.aslrecorder;

import android.content.Intent;
import android.os.Bundle;
import android.view.LayoutInflater;
import android.view.View;
import android.view.ViewGroup;

import androidx.annotation.NonNull;
import androidx.appcompat.app.AppCompatActivity;
import androidx.recyclerview.widget.LinearLayoutManager;
import androidx.recyclerview.widget.RecyclerView;

import com.example.aslrecorder.data.MetadataManager;
import com.example.aslrecorder.databinding.ActivitySignerProfileBinding;
import com.example.aslrecorder.databinding.ItemSignerBinding;
import com.example.aslrecorder.model.SignerProfile;

import java.util.List;

public class SignerProfileActivity extends AppCompatActivity {

    public static final String EXTRA_SIGNER = "extra_signer";

    private ActivitySignerProfileBinding binding;
    private MetadataManager metadataManager;
    private String autoSignerId;   // computed once on open, shown read-only

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        binding = ActivitySignerProfileBinding.inflate(getLayoutInflater());
        setContentView(binding.getRoot());

        metadataManager = new MetadataManager(this);

        binding.btnBack.setOnClickListener(v -> finish());

        setupSpinners();
        setupRecycler();

        // Compute and display the auto-assigned ID immediately
        autoSignerId = metadataManager.getNextSignerId();
        binding.tvAutoSignerId.setText(autoSignerId);
        binding.tvAutoSignerId.setContentDescription(
                "Unique signer ID. Collector " + metadataManager.getCollectorId());

        binding.btnNewSigner.setOnClickListener(v ->
                binding.btnNewSigner.setVisibility(View.GONE));

        binding.btnSaveProfile.setOnClickListener(v -> saveAndProceed());

        binding.spinnerSplit.setOnItemSelectedListener(
                new android.widget.AdapterView.OnItemSelectedListener() {
                    @Override
                    public void onItemSelected(android.widget.AdapterView<?> parent,
                                               View view, int position, long id) {
                        String split = (String) parent.getItemAtPosition(position);
                        binding.tvTestSignerWarning.setVisibility(
                                "test".equalsIgnoreCase(split) ? View.VISIBLE : View.GONE);
                    }
                    @Override public void onNothingSelected(android.widget.AdapterView<?> p) {}
                });
    }

    private void setupSpinners() {
        setSpinner(binding.spinnerDominantHand, new String[]{"Right", "Left", "Ambidextrous"});
        setSpinner(binding.spinnerAgeGroup,     new String[]{"18-25", "26-35", "36-50", "51-65", "65+"});
        setSpinner(binding.spinnerGender,       new String[]{"Male", "Female", "Non-binary", "Prefer not to say"});
        setSpinner(binding.spinnerExperience,   new String[]{"native", "fluent", "intermediate", "beginner"});
        setSpinner(binding.spinnerSplit,        new String[]{"train", "val", "test"});
    }

    private void setSpinner(android.widget.Spinner spinner, String[] items) {
        android.widget.ArrayAdapter<String> adapter = new android.widget.ArrayAdapter<>(
                this, android.R.layout.simple_spinner_item, items);
        adapter.setDropDownViewResource(android.R.layout.simple_spinner_dropdown_item);
        spinner.setAdapter(adapter);
    }

    private void setupRecycler() {
        List<SignerProfile> signers = metadataManager.loadSigners();
        binding.recyclerSigners.setLayoutManager(new LinearLayoutManager(this));
        binding.recyclerSigners.setAdapter(new SignerAdapter(signers));
    }

    private void saveAndProceed() {
        // ID was already computed when the screen opened — use it directly
        SignerProfile profile   = new SignerProfile();
        profile.signerId        = autoSignerId;
        profile.dominantHand    = (String) binding.spinnerDominantHand.getSelectedItem();
        profile.ageGroup        = (String) binding.spinnerAgeGroup.getSelectedItem();
        profile.gender          = (String) binding.spinnerGender.getSelectedItem();
        profile.signExperience  = (String) binding.spinnerExperience.getSelectedItem();
        profile.splitAssignment = (String) binding.spinnerSplit.getSelectedItem();
        profile.notes           = binding.etNotes.getText() == null
                ? "" : binding.etNotes.getText().toString().trim();

        metadataManager.saveSigner(profile);

        Intent intent = new Intent(this, SessionSetupActivity.class);
        intent.putExtra(SessionSetupActivity.EXTRA_SIGNER, profile);
        startActivity(intent);
        finish();
    }

    // ── Signer list adapter ───────────────────────────────────────────────────

    private class SignerAdapter extends RecyclerView.Adapter<SignerAdapter.VH> {
        private final List<SignerProfile> items;

        SignerAdapter(List<SignerProfile> items) { this.items = items; }

        @NonNull @Override
        public VH onCreateViewHolder(@NonNull ViewGroup parent, int viewType) {
            ItemSignerBinding b = ItemSignerBinding.inflate(
                    LayoutInflater.from(parent.getContext()), parent, false);
            return new VH(b);
        }

        @Override
        public void onBindViewHolder(@NonNull VH holder, int pos) { holder.bind(items.get(pos)); }

        @Override public int getItemCount() { return items.size(); }

        class VH extends RecyclerView.ViewHolder {
            final ItemSignerBinding b;
            VH(ItemSignerBinding b) { super(b.getRoot()); this.b = b; }

            void bind(SignerProfile p) {
                b.tvSignerItemId.setText(p.signerId);
                b.tvSignerItemDetail.setText(
                        p.ageGroup + " · " + p.gender
                                + " · " + p.dominantHand + " hand"
                                + " · " + p.splitAssignment);
                b.getRoot().setOnClickListener(v -> {
                    Intent intent = new Intent(
                            SignerProfileActivity.this, SessionSetupActivity.class);
                    intent.putExtra(SessionSetupActivity.EXTRA_SIGNER, p);
                    startActivity(intent);
                    finish();
                });
            }
        }
    }
}
