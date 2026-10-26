/**
 * Gateway API Client
 * Interfaces with unified reverse proxy endpoints and async job polling.
 */

export class ApiClient {
  constructor(baseUrl = '') {
    this.baseUrl = baseUrl;
  }

  async getConfig() {
    const res = await fetch(`${this.baseUrl}/api/config`);
    if (!res.ok) throw new Error(`Failed to load config: HTTP ${res.status}`);
    return await res.json();
  }

  async getHealth() {
    const res = await fetch(`${this.baseUrl}/api/health`);
    if (!res.ok) throw new Error(`Health check failed: HTTP ${res.status}`);
    return await res.json();
  }

  /**
   * Submit an evidence file for async processing.
   * Returns: { job_id, status, ... }
   */
  async submitJob(file, moduleId) {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('module_id', moduleId);

    const res = await fetch(`${this.baseUrl}/api/jobs`, {
      method: 'POST',
      body: formData,
    });

    if (!res.ok) {
      let errDetail = `HTTP ${res.status}`;
      try {
        const errJson = await res.json();
        if (errJson.detail) errDetail = errJson.detail;
      } catch (e) {}
      throw new Error(errDetail);
    }

    return await res.json();
  }

  /**
   * Poll status of an async job.
   */
  async pollJob(jobId) {
    const res = await fetch(`${this.baseUrl}/api/jobs/${jobId}`);
    if (!res.ok) throw new Error(`Job poll failed: HTTP ${res.status}`);
    return await res.json();
  }

  /**
   * Get direct artifact URL
   */
  getArtifactUrl(moduleId, filename) {
    // Map moduleId to proxy prefix
    const prefixMap = {
      ai_aud: '/api/aud/artifacts',
      ai_img: '/api/img/artifacts',
      image_forgery: '/api/forgery/artifacts',
      ai_cctv: '/api/cctv/artifacts',
    };
    const prefix = prefixMap[moduleId] || `/api/${moduleId}/artifacts`;
    // Clean filename if it already contains prefix
    const cleanName = filename.replace(/^artifacts\/[^\/]+\//, '').replace(/^artifacts\//, '');
    return `${this.baseUrl}${prefix}/${cleanName}`;
  }
}
