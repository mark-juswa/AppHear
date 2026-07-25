package com.example.apphear.ui.home

import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import androidx.recyclerview.widget.RecyclerView
import com.example.apphear.R

class FeatureCardAdapter(
    private val listener: Listener,
) : RecyclerView.Adapter<FeatureCardAdapter.CardViewHolder>() {

    interface Listener {
        fun onDetectClicked()
        fun onProjectClicked()
    }

    override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): CardViewHolder {
        val layoutId = if (viewType == CARD_DETECT) {
            R.layout.item_feature_card_detect
        } else {
            R.layout.item_feature_card_project
        }
        val view = LayoutInflater.from(parent.context).inflate(layoutId, parent, false)
        return CardViewHolder(view)
    }

    override fun onBindViewHolder(holder: CardViewHolder, position: Int) {
        if (position == CARD_DETECT) {
            holder.itemView.setOnClickListener { listener.onDetectClicked() }
            holder.itemView.findViewById<View>(R.id.btnStartSignDetect)
                ?.setOnClickListener { listener.onDetectClicked() }
        } else {
            holder.itemView.setOnClickListener { listener.onProjectClicked() }
            holder.itemView.findViewById<View>(R.id.btnStartTextToAsl)
                ?.setOnClickListener { listener.onProjectClicked() }
        }
    }

    override fun getItemCount(): Int = 2

    override fun getItemViewType(position: Int): Int = position

    class CardViewHolder(itemView: View) : RecyclerView.ViewHolder(itemView)

    private companion object {
        const val CARD_DETECT = 0
    }
}