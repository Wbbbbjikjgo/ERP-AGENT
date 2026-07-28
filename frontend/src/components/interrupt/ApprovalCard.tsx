"use client";

import { ShieldCheck, Check, X } from "lucide-react";
import { InterruptData } from "@/lib/types";

interface Props {
  data: InterruptData;
  onApprove: () => void;
  onReject: () => void;
}

export default function ApprovalCard({ data, onApprove, onReject }: Props) {
  const orderData = data.order_data || data.tool_args || {};

  return (
    <div className="mx-6 mb-3 animate-fade-in">
      <div className="max-w-3xl mx-auto border border-blue-200 bg-blue-50 rounded-xl p-4">
        <div className="flex items-center gap-2 mb-3">
          <ShieldCheck size={16} className="text-blue-600" />
          <span className="text-sm font-medium text-blue-800">
            订单审批确认
          </span>
        </div>

        <p className="text-xs text-blue-700 mb-3">
          以下操作需要您的审批确认：
          {data.tool_name && (
            <span className="font-medium"> {data.tool_name}</span>
          )}
        </p>

        {/* 订单详情 */}
        {Object.keys(orderData).length > 0 && (
          <div className="mb-4 p-3 bg-white/70 rounded-lg border border-blue-100">
            <table className="w-full text-xs">
              <tbody>
                {Object.entries(orderData).map(([key, value]) => (
                  <tr key={key} className="border-b border-blue-50 last:border-0">
                    <td className="py-1.5 pr-3 text-gray-500 font-medium whitespace-nowrap">
                      {key}
                    </td>
                    <td className="py-1.5 text-gray-800">
                      {typeof value === "object"
                        ? JSON.stringify(value)
                        : String(value)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* 审批按钮 */}
        <div className="flex gap-3">
          <button
            onClick={onApprove}
            className="flex items-center gap-1.5 px-4 py-2 bg-green-600 hover:bg-green-700 text-white text-sm font-medium rounded-lg transition-colors"
          >
            <Check size={14} />
            批准执行
          </button>
          <button
            onClick={onReject}
            className="flex items-center gap-1.5 px-4 py-2 bg-red-500 hover:bg-red-600 text-white text-sm font-medium rounded-lg transition-colors"
          >
            <X size={14} />
            拒绝
          </button>
        </div>
      </div>
    </div>
  );
}
