#ifdef WORKBENCH
//! Entrance snapping for placing tunnel and cave pieces by hand.
//!
//! Select the piece that stays put first, then one or more pieces to attach (ctrl-click), and run the plugin (Ctrl+Shift+J, or
//! the plugin menu). Every attached piece is turned and moved so one of its openings (the bones of its model, read from the
//! catalog as sockets) meets an opening of a piece that is already placed (the first, or one attached before it) and faces it:
//! same position, same height, opposite direction. The pair is the nearest compatible one (same size; a path with a path, a
//! doorframe with a doorway's room side). Run it again on the same two pieces, without touching them, and the next nearest
//! pair is tried, so a piece with several openings can be turned to the one you want.
//!
//! One undo step covers the whole run. Pieces are placed yaw-only, like the generator places them.

//! One compatible way to put a piece against another
class SP_SnapPair
{
	int m_iPlaced;			// which placed piece it goes against (index in the run's list)
	int m_iTargetSocket;	// that piece's socket
	int m_iMoverSocket;		// the moving piece's socket
	float m_fDist;			// how far the two sockets are now
	vector m_vPos;			// the moving piece's pose after the snap
	float m_fYaw;
}

//! A selected piece, with its pose
class SP_SnapPiece
{
	IEntitySource m_Src;
	IEntity m_Entity;
	int m_iPiece;		// catalog index
	string m_sName;
	vector m_vPos;
	float m_fYaw;
	ref array<bool> m_aTaken = {};		// per socket: already joined to something in this run
}

[WorkbenchPluginAttribute(name: "Entrance Snap", description: "Snap the selected pieces onto the first selected one by their openings (bones). The first stays, the others move.", shortcut: "Ctrl+Shift+J", wbModules: {"WorldEditor"}, awesomeFontCode: 0xF0C1)]
class SP_TunnelSnapPlugin : WorldEditorPlugin
{
	// (a plain int, as in the generator: with a script enum as its type the plugin didn't show up in the menu)
	[Attribute("1", UIWidgets.ComboBox, "Which pieces: the EoH Modular Tunnel Pack, or our own test kit (Prefabs/Tunnels/TT). The catalog is the one the generator built: rebuild it there when pieces are added", "", { ParamEnum("EoH Modular Tunnel Pack", "0"), ParamEnum("TT test kit", "1") }, category: "Snap")]
	protected int m_eKit;

	[Attribute("15", UIWidgets.EditBox, "Openings further apart than this, in metres, are not paired (a piece dropped far from the others is left alone, and says so)", category: "Snap")]
	protected float m_fReach;

	protected ref SP_TunnelCatalog m_Catalog;
	protected int m_iCatalogKit = -1;
	protected float m_fYawSign = 1;		// which way the editor turns an entity for a yaw; found out on the first run

	// Run it again on the same two pieces: the next pair
	protected IEntitySource m_LastMover;
	protected IEntitySource m_LastAnchor;
	protected vector m_vOrigPos;
	protected float m_fOrigYaw;
	protected vector m_vAppliedPos;
	protected float m_fAppliedYaw;
	protected int m_iCycle;

	//------------------------------------------------------------------------------------------------
	override void Run()
	{
		WorldEditor worldEditor = Workbench.GetModule(WorldEditor);
		if (!worldEditor)
			return;

		WorldEditorAPI api = worldEditor.GetApi();
		if (!api)
			return;

		if (!LoadCatalog(api))
			return;

		array<ref SP_SnapPiece> placed = {};
		array<ref SP_SnapPiece> movers = {};
		CollectSelected(api, placed, movers);
		if (placed.IsEmpty() || movers.IsEmpty())
		{
			Workbench.Dialog("Entrance Snap", "Select the piece that stays first, then ctrl-click the piece (or pieces) to attach to it. Only pieces of the catalog count (the TT kit's, or the EoH pack's). See the log for what was left out.");
			return;
		}

		// Run again on the same pair, with nothing touched since: the next pair, ranked from where the piece started
		bool again = false;
		if (movers.Count() == 1 && placed.Count() == 1 && movers[0].m_Src == m_LastMover && placed[0].m_Src == m_LastAnchor)
		{
			if (vector.Distance(movers[0].m_vPos, m_vAppliedPos) < 0.02 && Math.AbsFloat(SP_TunnelConnect.Wrap(movers[0].m_fYaw - m_fAppliedYaw)) < 0.5)
				again = true;
		}

		if (again)
		{
			movers[0].m_vPos = m_vOrigPos;
			movers[0].m_fYaw = m_fOrigYaw;
			m_iCycle++;
		}
		else
		{
			m_iCycle = 0;
		}

		array<ref SP_SnapPiece> moved = {};
		array<ref SP_SnapPair> chosen = {};
		api.BeginEntityAction("Entrance snap");
		foreach (SP_SnapPiece mover : movers)
		{
			SP_SnapPair pair = BestPair(placed, mover, m_iCycle);
			if (!pair)
			{
				Print(string.Format("SP_TunnelSnap: %1: no opening to join (see above), left where it is", mover.m_sName), LogLevel.WARNING);
				continue;
			}

			vector from = mover.m_vPos;
			float fromYaw = mover.m_fYaw;
			if (!again && movers.Count() == 1)
			{
				m_vOrigPos = from;
				m_fOrigYaw = fromYaw;
			}

			mover.m_vPos = pair.m_vPos;
			mover.m_fYaw = pair.m_fYaw;
			ApplyPose(api, mover.m_Src, pair.m_vPos, pair.m_fYaw);
			placed[pair.m_iPlaced].m_aTaken[pair.m_iTargetSocket] = true;
			mover.m_aTaken[pair.m_iMoverSocket] = true;
			placed.Insert(mover);
			moved.Insert(mover);
			chosen.Insert(pair);
			float travel = vector.Distance(from, pair.m_vPos);
			float turn = Math.AbsFloat(SP_TunnelConnect.Wrap(pair.m_fYaw - fromYaw));
			Print(string.Format("SP_TunnelSnap: %1: socket %2 onto %3 socket %4; moved %5 m, turned %6 degrees", mover.m_sName, pair.m_iMoverSocket + 1, placed[pair.m_iPlaced].m_sName, pair.m_iTargetSocket + 1, travel.ToString(-1, 2), Math.Round(turn)));
		}

		api.EndEntityAction();
		if (moved.IsEmpty())
			return;

		// Which way the editor turns for a yaw: look at what it did, and redo it the other way if it went wrong
		if (!YawIsRight(api, moved))
		{
			m_fYawSign = -m_fYawSign;
			Print("SP_TunnelSnap: the editor turns the other way: redoing the rotation with sign " + m_fYawSign.ToString(), LogLevel.WARNING);
			api.BeginEntityAction("Entrance snap (rotation fix)");
			foreach (SP_SnapPiece again2 : moved)
			{
				ApplyPose(api, again2.m_Src, again2.m_vPos, again2.m_fYaw);
			}

			api.EndEntityAction();
		}

		Report(api, placed, moved, chosen);
		if (moved.Count() == 1 && placed.Count() >= 2)
		{
			m_LastMover = moved[0].m_Src;
			m_LastAnchor = placed[chosen[0].m_iPlaced].m_Src;
			m_vAppliedPos = moved[0].m_vPos;
			m_fAppliedYaw = moved[0].m_fYaw;
		}
	}

	//------------------------------------------------------------------------------------------------
	override void Configure()
	{
		Workbench.ScriptDialog("Entrance Snap", "Select the piece that stays first, then ctrl-click the pieces to attach, then run the plugin (Ctrl+Shift+J). Run it again on the same pair, untouched, for the next pair of openings.", this);
	}

	//------------------------------------------------------------------------------------------------
	[ButtonAttribute("Close", true)]
	protected void ButtonClose()
	{
	}

	//------------------------------------------------------------------------------------------------
	protected bool LoadCatalog(WorldEditorAPI api)
	{
		if (m_Catalog && m_iCatalogKit == m_eKit && !m_Catalog.m_aPieces.IsEmpty())
			return true;

		m_Catalog = new SP_TunnelCatalog(m_eKit);
		m_iCatalogKit = m_eKit;
		if (m_Catalog.Get(api, false) && !m_Catalog.m_aPieces.IsEmpty())
			return true;

		Workbench.Dialog("Entrance Snap", "The piece catalog isn't there. Open the Tunnel Generator once and press Rebuild catalog (kit: " + m_eKit.ToString() + ").");
		return false;
	}

	//------------------------------------------------------------------------------------------------
	protected int PieceIndexOf(IEntitySource src, IEntity entity)
	{
		BaseContainer ancestor = src.GetAncestor();
		for (int depth = 0; depth < 6 && ancestor; depth++)
		{
			ResourceName ancestorName = ancestor.GetResourceName();
			if (!ancestorName.IsEmpty())
			{
				int found = m_Catalog.IndexOfPrefab(ancestorName);
				if (found >= 0)
					return found;
			}

			ancestor = ancestor.GetAncestor();
		}

		if (entity && entity.GetPrefabData())
			return m_Catalog.IndexOfPrefab(entity.GetPrefabData().GetPrefabName());

		return -1;
	}

	//------------------------------------------------------------------------------------------------
	//! The first selected catalog piece stays (placed); the other selected catalog pieces are to be moved
	protected void CollectSelected(WorldEditorAPI api, notnull array<ref SP_SnapPiece> placed, notnull array<ref SP_SnapPiece> movers)
	{
		for (int i = 0; i < api.GetSelectedEntitiesCount(); i++)
		{
			IEntitySource src = api.GetSelectedEntity(i);
			if (!src)
				continue;

			IEntity entity = api.SourceToEntity(src);
			if (!entity)
				continue;

			int index = PieceIndexOf(src, entity);
			if (index < 0)
			{
				Print(string.Format("SP_TunnelSnap: '%1' is not a piece of the catalog (kit %2): left out", src.GetName(), m_eKit), LogLevel.WARNING);
				continue;
			}

			vector mat[4];
			entity.GetWorldTransform(mat);
			SP_SnapPiece piece = new SP_SnapPiece();
			piece.m_Src = src;
			piece.m_Entity = entity;
			piece.m_iPiece = index;
			piece.m_sName = m_Catalog.m_aPieces[index].m_sName;
			if (!src.GetName().IsEmpty())
				piece.m_sName = src.GetName();

			piece.m_vPos = mat[3];
			piece.m_fYaw = SP_TunnelGrower.YawOf(mat[2]);
			foreach (SP_TunnelSocketDef unusedSocket : m_Catalog.m_aPieces[index].m_aSockets)
			{
				piece.m_aTaken.Insert(false);
			}

			if (placed.IsEmpty())
				placed.Insert(piece);
			else
				movers.Insert(piece);
		}
	}

	//------------------------------------------------------------------------------------------------
	protected bool Compatible(SP_TunnelSocketDef a, SP_TunnelSocketDef b)
	{
		if (a.m_iSize != b.m_iSize)
			return false;

		if (a.m_iRole == SP_TunnelRole.PATH && b.m_iRole == SP_TunnelRole.PATH)
			return true;

		if (a.m_iRole == SP_TunnelRole.DOOR && b.m_iRole == SP_TunnelRole.ROOMSIDE)
			return true;

		if (a.m_iRole == SP_TunnelRole.ROOMSIDE && b.m_iRole == SP_TunnelRole.DOOR)
			return true;

		return false;
	}

	//------------------------------------------------------------------------------------------------
	//! The nearest compatible pair (or, for cycle > 0, the one that far down the list, wrapping round) of one of the mover's
	//! free sockets and a free socket of a placed piece, with the pose the mover would get. null: nothing to join
	protected SP_SnapPair BestPair(notnull array<ref SP_SnapPiece> placed, SP_SnapPiece mover, int cycle)
	{
		SP_TunnelPieceDef moverDef = m_Catalog.m_aPieces[mover.m_iPiece];
		array<ref SP_SnapPair> pairs = {};
		int tooFar = 0;
		int incompatible = 0;
		foreach (int p, SP_SnapPiece target : placed)
		{
			SP_TunnelPieceDef targetDef = m_Catalog.m_aPieces[target.m_iPiece];
			foreach (int t, SP_TunnelSocketDef targetSocket : targetDef.m_aSockets)
			{
				if (target.m_aTaken[t])
					continue;

				vector openPos = target.m_vPos + SP_TunnelGrower.Rot(targetSocket.m_vPos, target.m_fYaw);
				vector openDir = SP_TunnelGrower.Rot(targetSocket.m_vDir, target.m_fYaw);
				foreach (int m, SP_TunnelSocketDef moverSocket : moverDef.m_aSockets)
				{
					if (mover.m_aTaken[m])
						continue;

					if (!Compatible(targetSocket, moverSocket))
					{
						incompatible++;
						continue;
					}

					vector now = mover.m_vPos + SP_TunnelGrower.Rot(moverSocket.m_vPos, mover.m_fYaw);
					float dist = vector.Distance(now, openPos);
					if (dist > m_fReach)
					{
						tooFar++;
						continue;
					}

					SP_SnapPair pair = new SP_SnapPair();
					pair.m_iPlaced = p;
					pair.m_iTargetSocket = t;
					pair.m_iMoverSocket = m;
					pair.m_fDist = dist;
					SP_TunnelGrower.Attach(openPos, openDir, moverSocket, pair.m_vPos, pair.m_fYaw);

					// nearest first
					int at = pairs.Count();
					while (at > 0 && pairs[at - 1].m_fDist > dist)
					{
						at--;
					}

					pairs.InsertAt(pair, at);
				}
			}
		}

		if (pairs.IsEmpty())
		{
			if (incompatible > 0 && tooFar == 0)
				Print(string.Format("SP_TunnelSnap: %1: none of its openings fits a free opening of the others (different size or kind)", mover.m_sName), LogLevel.WARNING);
			else if (tooFar > 0)
				Print(string.Format("SP_TunnelSnap: %1: its openings are all further than %2 m from a matching free opening (raise Reach in Configure, or drop it closer)", mover.m_sName, m_fReach.ToString(-1, 0)), LogLevel.WARNING);
			else
				Print(string.Format("SP_TunnelSnap: %1: no free opening left on the pieces before it", mover.m_sName), LogLevel.WARNING);

			return null;
		}

		return pairs[cycle % pairs.Count()];
	}

	//------------------------------------------------------------------------------------------------
	protected void ApplyPose(WorldEditorAPI api, IEntitySource src, vector pos, float yaw)
	{
		api.SetVariableValue(src, null, "coords", pos.ToString(false));
		api.SetVariableValue(src, null, "angleY", (yaw * m_fYawSign).ToString());
	}

	//------------------------------------------------------------------------------------------------
	//! Did the editor turn every moved piece to the yaw that was meant? (Its forward is read back from the entity.)
	protected bool YawIsRight(WorldEditorAPI api, notnull array<ref SP_SnapPiece> moved)
	{
		foreach (SP_SnapPiece piece : moved)
		{
			IEntity entity = api.SourceToEntity(piece.m_Src);
			if (!entity)
				continue;

			vector mat[4];
			entity.GetWorldTransform(mat);
			float actual = SP_TunnelGrower.YawOf(mat[2]);
			float error = Math.AbsFloat(SP_TunnelConnect.Wrap(actual - piece.m_fYaw));
			if (error > 2)
				return false;
		}

		return true;
	}

	//------------------------------------------------------------------------------------------------
	//! One line per moved piece: how well the openings meet, read back from the entities as they are now
	protected void Report(WorldEditorAPI api, notnull array<ref SP_SnapPiece> placed, notnull array<ref SP_SnapPiece> moved, notnull array<ref SP_SnapPair> chosen)
	{
		foreach (int k, SP_SnapPiece piece : moved)
		{
			SP_SnapPair pair = chosen[k];
			SP_SnapPiece target = placed[pair.m_iPlaced];
			IEntity moverEntity = api.SourceToEntity(piece.m_Src);
			IEntity targetEntity = api.SourceToEntity(target.m_Src);
			if (!moverEntity || !targetEntity)
				continue;

			vector moverMat[4];
			vector targetMat[4];
			moverEntity.GetWorldTransform(moverMat);
			targetEntity.GetWorldTransform(targetMat);
			SP_TunnelSocketDef moverSocket = m_Catalog.m_aPieces[piece.m_iPiece].m_aSockets[pair.m_iMoverSocket];
			SP_TunnelSocketDef targetSocket = m_Catalog.m_aPieces[target.m_iPiece].m_aSockets[pair.m_iTargetSocket];
			float moverYaw = SP_TunnelGrower.YawOf(moverMat[2]);
			float targetYaw = SP_TunnelGrower.YawOf(targetMat[2]);
			vector moverPos = moverMat[3] + SP_TunnelGrower.Rot(moverSocket.m_vPos, moverYaw);
			vector targetPos = targetMat[3] + SP_TunnelGrower.Rot(targetSocket.m_vPos, targetYaw);
			float gap = vector.Distance(moverPos, targetPos);
			float facing = SP_TunnelGrower.YawOf(SP_TunnelGrower.Rot(moverSocket.m_vDir, moverYaw)) - SP_TunnelGrower.YawOf(SP_TunnelGrower.Rot(targetSocket.m_vDir, targetYaw));
			float facingError = Math.AbsFloat(SP_TunnelConnect.Wrap(facing - 180));
			string verdict = "joined";
			if (gap > 0.02 || facingError > 1)
				verdict = "NOT exact (is the entity scaled, tilted or parented?)";

			float gapCm = gap * 100;
			Print(string.Format("SP_TunnelSnap:   %1 %2: gap %3 cm, facing off by %4 degrees", piece.m_sName, verdict, gapCm.ToString(-1, 1), facingError.ToString(-1, 1)));
		}
	}
}
#endif
