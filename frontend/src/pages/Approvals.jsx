import React, { useEffect, useState } from "react";
import { useAuth } from "../auth/AuthContext";
import { getApprovals, approveMutation, rejectMutation, executeMutation, retryMutation } from "../api/mutations";

export default function Approvals() {
  const { user } = useAuth();
  const [approvalsList, setApprovalsList] = useState([]);
  const [loadingAction, setLoadingAction] = useState(null);
  
  const load = () => {
    getApprovals().then(setApprovalsList).catch(console.error);
  };
  
  useEffect(() => { load(); }, []);
  
  const handleApprove = async (id) => {
    setLoadingAction(id);
    try {
      await approveMutation(id);
      // Immediately execute
      await executeMutation(id);
      alert("Approved and execution attempted. Check audit logs.");
      load();
    } catch (e) {
      console.error(e);
      alert("Failed to approve/execute");
    } finally {
      setLoadingAction(null);
    }
  };

  const handleReject = async (id) => {
    setLoadingAction(id);
    try {
      await rejectMutation(id);
      load();
    } catch (e) {
      console.error(e);
      alert("Failed to reject");
    } finally {
      setLoadingAction(null);
    }
  };

  const handleRetry = async (id) => {
    setLoadingAction(id);
    try {
      await retryMutation(id);
      alert("Retry execution attempted.");
      load();
    } catch (e) {
      console.error(e);
      alert("Failed to retry");
    } finally {
      setLoadingAction(null);
    }
  };
  
  return (
    <>
      <header>
        <div>
          <h1>Approvals & Execution Audit</h1>
          <p>Human-in-the-loop control and mutation recovery.</p>
        </div>
      </header>
      <section className="card">
        {approvalsList.map(a => (
          <div className="approval" key={a.id}>
            <div>
              <b>{a.summary}</b>
              <small>Requested by {a.requested_by} on {new Date(a.created_at).toLocaleString()}</small>
              <br />
              {a.platform && <small className="badge">{a.platform}</small>}
            </div>
            
            {a.status === "pending" ? (
              user.role === 'manager' ? (
                <div>
                  <button 
                    onClick={() => handleApprove(a.id)} 
                    disabled={loadingAction === a.id}
                  >Approve</button>
                  <button 
                    className="danger" 
                    onClick={() => handleReject(a.id)}
                    disabled={loadingAction === a.id}
                  >Reject</button>
                </div>
              ) : (
                <span className="badge">Pending Manager Review</span>
              )
            ) : (
              <div>
                <span className="badge">{a.status}</span>
                {/* Basic visual for retry logic for failed_retryable, if frontend knows audit status it would go here */}
                {a.status === 'approved' && user.role === 'manager' && (
                  <button style={{marginLeft: 10}} onClick={() => handleRetry(a.id)} disabled={loadingAction === a.id}>Retry Execution</button>
                )}
              </div>
            )}
          </div>
        ))}
      </section>
    </>
  );
}
