import { Component, ReactNode } from 'react'

type Props = {
  fallback: ReactNode
  children: ReactNode
}

type State = { hasError: boolean }

export class VisualErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false }

  static getDerivedStateFromError(): State {
    return { hasError: true }
  }

  componentDidCatch(error: Error) {
    console.error('Visual component failed to render, falling back to bullets:', error)
  }

  render() {
    if (this.state.hasError) {
      return this.props.fallback
    }
    return this.props.children
  }
}
