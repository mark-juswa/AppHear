package com.example.aslrecorder;

import android.content.Intent;
import android.net.Uri;
import android.os.Bundle;
import android.view.LayoutInflater;
import android.view.View;
import android.view.ViewGroup;
import android.widget.TextView;
import android.widget.Toast;

import androidx.annotation.NonNull;
import androidx.appcompat.app.AppCompatActivity;
import androidx.core.content.FileProvider;
import androidx.recyclerview.widget.LinearLayoutManager;
import androidx.recyclerview.widget.RecyclerView;

import com.example.aslrecorder.data.DatasetFileManager;
import com.example.aslrecorder.databinding.ActivityDatasetBrowserBinding;

import java.io.File;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Comparator;
import java.util.List;

public class DatasetBrowserActivity extends AppCompatActivity {

    private ActivityDatasetBrowserBinding binding;
    private File datasetRoot;
    private File currentDir;
    private DatasetAdapter adapter;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        binding = ActivityDatasetBrowserBinding.inflate(getLayoutInflater());
        setContentView(binding.getRoot());

        datasetRoot = new DatasetFileManager(this).getDatasetRoot();
        currentDir = datasetRoot;

        adapter = new DatasetAdapter();
        binding.recyclerDataset.setLayoutManager(new LinearLayoutManager(this));
        binding.recyclerDataset.setAdapter(adapter);
        binding.btnBack.setOnClickListener(v -> navigateBack());

        loadCurrentDir();
    }

    @Override
    public void onBackPressed() {
        navigateBack();
    }

    private void navigateBack() {
        if (currentDir != null && !sameFile(currentDir, datasetRoot)) {
            currentDir = currentDir.getParentFile();
            loadCurrentDir();
        } else {
            finish();
        }
    }

    private void loadCurrentDir() {
        if (currentDir == null || !isInsideDataset(currentDir)) {
            currentDir = datasetRoot;
        }

        binding.tvCurrentPath.setText(relativePath(currentDir));

        File[] files = currentDir.listFiles();
        List<File> items = new ArrayList<>();
        if (files != null) {
            items.addAll(Arrays.asList(files));
            items.sort(Comparator
                    .comparing((File f) -> !f.isDirectory())
                    .thenComparing(f -> f.getName().toLowerCase()));
        }

        binding.tvEmpty.setVisibility(items.isEmpty() ? View.VISIBLE : View.GONE);
        adapter.setItems(items);
    }

    private void openItem(File file) {
        if (file.isDirectory()) {
            currentDir = file;
            loadCurrentDir();
            return;
        }

        Uri uri = FileProvider.getUriForFile(
                this, getPackageName() + ".fileprovider", file);
        Intent intent = new Intent(Intent.ACTION_VIEW);
        intent.setDataAndType(uri, mimeType(file));
        intent.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);

        try {
            startActivity(Intent.createChooser(intent, file.getName()));
        } catch (Exception e) {
            Toast.makeText(this, "No app can open this file.", Toast.LENGTH_SHORT).show();
        }
    }

    private String mimeType(File file) {
        String name = file.getName().toLowerCase();
        if (name.endsWith(".json")) return "application/json";
        if (name.endsWith(".csv")) return "text/csv";
        if (name.endsWith(".txt")) return "text/plain";
        if (name.endsWith(".zip")) return "application/zip";
        return "*/*";
    }

    private String relativePath(File file) {
        String rootPath = datasetRoot.getAbsolutePath();
        String filePath = file.getAbsolutePath();
        if (sameFile(file, datasetRoot)) return "AppHearDataset";
        if (filePath.startsWith(rootPath)) {
            return "AppHearDataset" + filePath.substring(rootPath.length());
        }
        return filePath;
    }

    private boolean isInsideDataset(File file) {
        try {
            String rootPath = datasetRoot.getCanonicalPath();
            String filePath = file.getCanonicalPath();
            return filePath.equals(rootPath) || filePath.startsWith(rootPath + File.separator);
        } catch (Exception e) {
            return false;
        }
    }

    private boolean sameFile(File a, File b) {
        try {
            return a.getCanonicalPath().equals(b.getCanonicalPath());
        } catch (Exception e) {
            return a.equals(b);
        }
    }

    private class DatasetAdapter extends RecyclerView.Adapter<DatasetAdapter.VH> {
        private final List<File> items = new ArrayList<>();

        void setItems(List<File> newItems) {
            items.clear();
            items.addAll(newItems);
            notifyDataSetChanged();
        }

        @NonNull
        @Override
        public VH onCreateViewHolder(@NonNull ViewGroup parent, int viewType) {
            View view = LayoutInflater.from(parent.getContext())
                    .inflate(android.R.layout.simple_list_item_2, parent, false);
            return new VH(view);
        }

        @Override
        public void onBindViewHolder(@NonNull VH holder, int position) {
            File file = items.get(position);
            holder.title.setText((file.isDirectory() ? "[Folder] " : "[File] ") + file.getName());
            holder.subtitle.setText(file.isDirectory()
                    ? "Open folder"
                    : file.length() + " bytes");
            holder.itemView.setOnClickListener(v -> openItem(file));
        }

        @Override
        public int getItemCount() {
            return items.size();
        }

        class VH extends RecyclerView.ViewHolder {
            final TextView title;
            final TextView subtitle;

            VH(@NonNull View itemView) {
                super(itemView);
                title = itemView.findViewById(android.R.id.text1);
                subtitle = itemView.findViewById(android.R.id.text2);
                title.setTextColor(getColor(R.color.text_primary));
                subtitle.setTextColor(getColor(R.color.text_secondary));
            }
        }
    }
}
