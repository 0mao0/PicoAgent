import type { DocumentResponse } from '@angineer/docs-ui'
import { docsApiClient } from '../../../shared/apiClient'

export const knowledgeApi = {
  getLibraries: () => docsApiClient.get<{ id: string; name: string }[]>('/knowledge/libraries'),

  getDocument: (libraryId: string, docId: string) =>
    docsApiClient.get<DocumentResponse>(`/knowledge/document/${libraryId}/${docId}`),

  getDocBlocksGraph: (libraryId: string, docId: string) =>
    docsApiClient.post('/knowledge/parse/doc-blocks-graph', { library_id: libraryId, doc_id: docId })
}

export default docsApiClient
