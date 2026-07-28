"use client";

export default function Logo() {
  return (
    <div className="flex items-center gap-3 px-4 py-5">
      <div className="w-9 h-9 rounded-lg bg-[#2563EB] flex items-center justify-center">
        <span className="text-white font-bold text-sm">采</span>
      </div>
      <div className="flex flex-col">
        <span className="text-sm font-semibold text-gray-900">智能采购助手</span>
        <span className="text-[11px] text-gray-400">ERP Agent</span>
      </div>
    </div>
  );
}
