"use client";

import { InterruptData } from "@/lib/types";
import SupplementForm from "./SupplementForm";
import ApprovalCard from "./ApprovalCard";

interface Props {
  data: InterruptData;
  onSupplement: (text: string) => void;
  onApprove: () => void;
  onReject: () => void;
}

export default function InterruptBanner({
  data,
  onSupplement,
  onApprove,
  onReject,
}: Props) {
  if (data.interrupt_type === "order_info_supplement") {
    return <SupplementForm data={data} onSubmit={onSupplement} />;
  }

  if (data.interrupt_type === "hitl_approval") {
    return <ApprovalCard data={data} onApprove={onApprove} onReject={onReject} />;
  }

  return null;
}
